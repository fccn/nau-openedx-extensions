"""
Tests for the installation into the LMS settings, plus the conformance checks of what it assumes about
edx-platform.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from nau_openedx_extensions.read_replica import registration

CSMH_ROUTER = "openedx.core.lib.django_courseware_routers.StudentModuleHistoryExtendedRouter"


def lms_settings(**overrides):
    """
    Return a stand in for the LMS settings module with the entries the registration looks at.
    """
    values = {
        "DATABASE_ROUTERS": [CSMH_ROUTER, registration.UPSTREAM_ROUTER],
        "MIDDLEWARE": ["first.Middleware", "second.Middleware", registration.LAST_MIDDLEWARE],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class RegisterGetRoutingTest(SimpleTestCase):
    """
    What the registration does to the settings.
    """

    def test_the_router_is_replaced_in_place(self):
        """The order of the routers is kept, and Tutor can still remove the other one by name."""
        settings = lms_settings()
        registration.register_get_routing(settings)
        self.assertEqual(settings.DATABASE_ROUTERS, [CSMH_ROUTER, registration.NAU_ROUTER])
        settings.DATABASE_ROUTERS.remove(CSMH_ROUTER)

    def test_the_middleware_goes_before_the_site_configuration_middleware(self):
        """The platform wants its site configuration middleware at the end of the list."""
        settings = lms_settings()
        registration.register_get_routing(settings)
        self.assertEqual(
            settings.MIDDLEWARE,
            ["first.Middleware", "second.Middleware", registration.MIDDLEWARE, registration.LAST_MIDDLEWARE],
        )

    def test_it_is_added_at_the_end_if_the_last_middleware_is_gone(self):
        """A platform upgrade that renames the last middleware must not break the start-up."""
        settings = lms_settings(MIDDLEWARE=["first.Middleware"])
        registration.register_get_routing(settings)
        self.assertEqual(settings.MIDDLEWARE, ["first.Middleware", registration.MIDDLEWARE])

    def test_calling_it_twice_changes_nothing_more(self):
        """The registration is idempotent."""
        settings = lms_settings()
        registration.register_get_routing(settings)
        once = (list(settings.DATABASE_ROUTERS), list(settings.MIDDLEWARE))
        registration.register_get_routing(settings)
        self.assertEqual((settings.DATABASE_ROUTERS, settings.MIDDLEWARE), once)

    def test_without_the_upstream_router_nothing_is_installed(self):
        """
        The Studio registers no read replica router, and an emptied router list must not break the start-up.
        There is nothing to extend, so the middleware is not added either.
        """
        for routers in ([CSMH_ROUTER], []):
            with self.subTest(routers=routers):
                settings = lms_settings(DATABASE_ROUTERS=list(routers))
                with self.assertLogs("nau_openedx_extensions.read_replica.registration", level="WARNING"):
                    registration.register_get_routing(settings)
                self.assertEqual(settings.DATABASE_ROUTERS, routers)
                self.assertNotIn(registration.MIDDLEWARE, settings.MIDDLEWARE)


class PlatformConformanceTest(SimpleTestCase):
    """
    The assumptions the registration makes about edx-platform. If an upgrade breaks one, the routing is silently
    not installed, so this fails the upgrade instead.
    """

    def test_the_lms_registers_the_upstream_router_and_the_site_configuration_middleware(self):
        """The two names the registration looks for are in the LMS defaults."""
        from lms.envs import common  # pylint: disable=import-error,import-outside-toplevel

        self.assertIn(registration.UPSTREAM_ROUTER, common.DATABASE_ROUTERS)
        self.assertIn(registration.LAST_MIDDLEWARE, common.MIDDLEWARE)

    def test_the_dotted_paths_can_be_imported(self):
        """The router and the middleware that are registered by name exist."""
        from django.utils.module_loading import import_string  # pylint: disable=import-outside-toplevel

        for path in (registration.NAU_ROUTER, registration.MIDDLEWARE):
            with self.subTest(path=path):
                self.assertTrue(import_string(path))
