"""
Middleware that keeps the plain CMS Django session alive for users who are only making
JWT-authenticated requests (e.g. via the authoring MFE), which never otherwise touch or
resave it.
"""
from typing import Callable

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.core.cache import cache
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse

SESSION_TOUCH_CACHE_KEY = "nau_session_touch:{}"


class TouchSessionMiddleware:  # pylint: disable=too-few-public-methods
    """
    Debounced session keep-alive. A session with its own logged-in user (SESSION_KEY in
    session, not just request.user -- a JWT-authenticated request can have an authenticated
    request.user over an otherwise anonymous session, e.g. mid SSO dance) is marked modified
    at most once per touch interval, instead of on every request, so SessionMiddleware/
    SafeSessionMiddleware resave and re-sign it before it can go stale from inactivity
    (fccn/nau-technical#1036).

    The touch re-saves the session as it was loaded at the start of the request, so a key
    written by a concurrent request can still be overwritten -- at most once per interval per
    session, since the debounce gate below limits touches, not regular session-modifying
    requests. Accepted, because only a few CMS paths write to the session (import status,
    VIDEOS_PER_PAGE, messages, login/SSO, XBlock preview state).

    Must sit after SessionMiddleware (and SafeSessionMiddleware) in MIDDLEWARE so this change
    to session.modified is seen by their response-phase processing.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not getattr(settings, "NAU_SESSION_TOUCH_ENABLED", True):
            raise MiddlewareNotUsed()
        self.get_response = get_response
        # Evaluated once, so a bad value fails when the workers start and not on every request. A zero or
        # negative interval would make cache.add() succeed every time and touch the session on every request.
        self.interval = max(
            1,
            min(int(getattr(settings, "NAU_SESSION_TOUCH_INTERVAL_SECONDS", 600)), settings.SESSION_COOKIE_AGE // 4),
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        session = getattr(request, "session", None)
        if session is None or session.modified or SESSION_KEY not in session or not session.session_key:
            return response

        # Atomic gate, checked first so that most requests cost a single cache round trip: with several
        # overlapping requests only the first one to add this key within the interval touches the session.
        if not cache.add(SESSION_TOUCH_CACHE_KEY.format(session.session_key), 1, self.interval):
            return response

        # The exists() check narrows, but does not close, the window where the session is
        # deleted concurrently (e.g. a logout in another tab) between being loaded and here.
        if session.exists(session.session_key):
            session.modified = True

        return response
