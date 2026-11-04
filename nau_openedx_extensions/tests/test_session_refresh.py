"""
Tests for the session keep-alive middleware.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.backends.cache import SessionStore
from django.core.cache import cache
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import override_settings

from nau_openedx_extensions.settings.common import (
    _append_middleware,
    _register_session_touch_middleware,
    plugin_settings,
)
from nau_openedx_extensions.studio.session_refresh import SESSION_TOUCH_CACHE_KEY, TouchSessionMiddleware

LOCMEM_CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
MIDDLEWARE = "nau_openedx_extensions.studio.session_refresh.TouchSessionMiddleware"


@override_settings(CACHES=LOCMEM_CACHES)
class TouchSessionMiddlewareTest(TestCase):
    """
    Test the middleware that keeps a Studio session with its own logged-in user alive.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def make_session(self, logged_in=True, extra_data=None, save=True):
        """Return a new, optionally saved, session."""
        session = SessionStore()
        if logged_in:
            session[SESSION_KEY] = 1
        if extra_data:
            session.update(extra_data)
        if save:
            session.save()
        # A freshly-loaded session for an incoming request always starts unmodified; building
        # one up here (via __setitem__/update()/save()) leaves .modified=True as a side effect.
        session.modified = False
        return session

    def request_for(self, session):
        """Return a request carrying the given session."""
        request = RequestFactory().get("/xblock/some-block")
        request.session = session
        return request

    def reload_request(self, session_key):
        """Return a request with a freshly-loaded session for an existing key, simulating a new,
        independent request arriving with the same session cookie (unlike reusing the same Python
        session object, whose `.modified` flag would otherwise leak between calls)."""
        return self.request_for(SessionStore(session_key=session_key))

    def handle(self, request, get_response=None):
        """Run the middleware and return the response."""
        get_response = get_response or (lambda req: HttpResponse())
        return TouchSessionMiddleware(get_response)(request)

    def test_touches_a_never_touched_session(self):
        """The session is marked modified the first time it is seen."""
        request = self.request_for(self.make_session())

        self.handle(request)

        self.assertTrue(request.session.modified)

    def test_touches_again_once_the_interval_elapsed(self):
        """Once the debounce gate has expired, a new request touches the session again."""
        session = self.make_session()
        self.handle(self.request_for(session))
        cache.delete(SESSION_TOUCH_CACHE_KEY.format(session.session_key))

        second_request = self.reload_request(session.session_key)
        self.handle(second_request)

        self.assertTrue(second_request.session.modified)

    def test_no_touch_inside_the_interval(self):
        """A second, independent request within the interval does not touch the session again."""
        session = self.make_session()
        self.handle(self.request_for(session))

        second_request = self.reload_request(session.session_key)
        self.handle(second_request)

        self.assertFalse(second_request.session.modified)

    @override_settings(SESSION_COOKIE_AGE=40, NAU_SESSION_TOUCH_INTERVAL_SECONDS=600)
    def test_interval_follows_a_short_session_cookie_age(self):
        """The debounce interval is clamped to SESSION_COOKIE_AGE // 4, not just the configured default."""
        request = self.request_for(self.make_session())

        with patch("nau_openedx_extensions.studio.session_refresh.cache.add") as mock_add:
            mock_add.return_value = True
            self.handle(request)

        self.assertEqual(mock_add.call_args.args[-1], 10)  # 40 // 4, not the configured 600

    def test_empty_session_is_not_recreated(self):
        """An expired/never-saved session is not resurrected."""
        request = self.request_for(self.make_session(save=False))

        self.handle(request)

        self.assertFalse(request.session.modified)

    def test_session_without_a_logged_in_user_is_not_touched(self):
        """A session that exists but has no user of its own (e.g. mid SSO dance) is left alone."""
        request = self.request_for(self.make_session(logged_in=False, extra_data={"edx-oauth2_state": "abc"}))

        self.handle(request)

        self.assertFalse(request.session.modified)

    def test_a_view_modified_session_is_left_alone(self):
        """A request whose view already modified the session is not additionally gated/touched."""
        request = self.request_for(self.make_session())

        def get_response(req):
            req.session["some_key"] = "some_value"
            return HttpResponse()

        self.handle(request, get_response=get_response)

        # Still modified (by the view itself), but the middleware never added its own gate key.
        self.assertTrue(request.session.modified)
        self.assertIsNone(cache.get(SESSION_TOUCH_CACHE_KEY.format(request.session.session_key)))

    def test_response_is_returned_unchanged(self):
        """The middleware returns the exact response object from the view."""
        request = self.request_for(self.make_session())
        expected_response = HttpResponse("hello")

        response = self.handle(request, get_response=lambda req: expected_response)

        self.assertIs(response, expected_response)

    def test_request_without_a_session_attribute_does_not_break(self):
        """A request that never went through SessionMiddleware at all is handled safely."""
        request = RequestFactory().get("/xblock/some-block")

        response = self.handle(request)

        self.assertIsInstance(response, HttpResponse)

    def test_deleted_session_is_not_touched(self):
        """A session deleted concurrently (e.g. a logout in another tab) is not resurrected by a touch."""
        session = self.make_session()
        session.delete()
        request = self.reload_request(session.session_key)

        self.handle(request)

        self.assertFalse(request.session.modified)

    def test_session_deleted_while_the_request_is_in_flight_is_not_touched(self):
        """A logout in another tab after the session was loaded must not end up as a SessionInterrupted (HTTP 400)."""
        session = self.make_session()
        request = self.reload_request(session.session_key)

        def get_response(req):
            self.assertIn(SESSION_KEY, req.session)  # the session is loaded by the request...
            SessionStore(session_key=session.session_key).delete()  # ...then deleted by a concurrent request
            return HttpResponse()

        self.handle(request, get_response=get_response)

        self.assertFalse(request.session.modified)

    @override_settings(NAU_SESSION_TOUCH_INTERVAL_SECONDS=0)
    def test_a_zero_interval_does_not_touch_on_every_request(self):
        """cache.add() with a timeout of 0 stores nothing and always succeeds: the interval is kept at 1s or more."""
        request = self.request_for(self.make_session())

        with patch("nau_openedx_extensions.studio.session_refresh.cache.add") as mock_add:
            mock_add.return_value = False
            self.handle(request)

        self.assertEqual(mock_add.call_args.args[-1], 1)

    @override_settings(NAU_SESSION_TOUCH_INTERVAL_SECONDS="600")
    def test_an_interval_set_as_a_string_is_accepted(self):
        """A value coming from the env tokens as a string does not break every request."""
        request = self.request_for(self.make_session())

        self.handle(request)

        self.assertTrue(request.session.modified)

    def test_a_request_inside_the_interval_makes_a_single_cache_round_trip(self):
        """The gate is checked before exists(), so requests that are not due do not pay for it."""
        session = self.make_session()
        self.handle(self.request_for(session))
        second_request = self.reload_request(session.session_key)

        with patch.object(SessionStore, "exists") as mock_exists:
            self.handle(second_request)

        mock_exists.assert_not_called()

    @override_settings(NAU_SESSION_TOUCH_ENABLED=False)
    def test_disabled(self):
        """The middleware is not used when disabled."""
        with self.assertRaises(MiddlewareNotUsed):
            TouchSessionMiddleware(lambda request: HttpResponse())


class SessionTouchSettingsTest(SimpleTestCase):
    """
    Test that the plugin registers the middleware for CMS only.
    """

    def test_registered_once_for_cms(self):
        """The middleware is added for CMS, and only once even if the plugin hook runs twice."""
        settings = SimpleNamespace(SERVICE_VARIANT="cms", MIDDLEWARE=[])

        _register_session_touch_middleware(settings)
        _register_session_touch_middleware(settings)

        self.assertEqual(settings.MIDDLEWARE.count(MIDDLEWARE), 1)

    def test_plugin_hook_registers_it_for_cms_only(self):
        """The plugin hook itself, and not only the helper, registers the middleware for CMS and not for LMS."""
        cms_settings = MagicMock(SERVICE_VARIANT="cms", MIDDLEWARE=[], OPEN_EDX_FILTERS_CONFIG={})
        lms_settings = MagicMock(SERVICE_VARIANT="lms", MIDDLEWARE=[], OPEN_EDX_FILTERS_CONFIG={})

        plugin_settings(cms_settings)
        plugin_settings(lms_settings)

        self.assertEqual(cms_settings.MIDDLEWARE.count(MIDDLEWARE), 1)
        self.assertNotIn(MIDDLEWARE, lms_settings.MIDDLEWARE)

    def test_not_registered_for_lms(self):
        """The middleware is not added when running as LMS."""
        settings = SimpleNamespace(SERVICE_VARIANT="lms", MIDDLEWARE=[])

        _register_session_touch_middleware(settings)

        self.assertNotIn(MIDDLEWARE, settings.MIDDLEWARE)


class AppendMiddlewareTest(SimpleTestCase):
    """
    Test adding a middleware to MIDDLEWARE.
    """

    def test_appends_once(self):
        """The middleware is appended, and not duplicated on a second call."""
        settings = SimpleNamespace(MIDDLEWARE=["some.other.Middleware"])

        _append_middleware(settings, MIDDLEWARE)
        _append_middleware(settings, MIDDLEWARE)

        self.assertEqual(settings.MIDDLEWARE, ["some.other.Middleware", MIDDLEWARE])
