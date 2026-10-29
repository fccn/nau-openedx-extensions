# -*- coding: utf-8 -*-
"""
Keeps the plain CMS Django session alive for users who are only making
JWT-authenticated requests (e.g. via the authoring MFE), which never otherwise
touch/resave the session. Without this, a session left untouched for
SESSION_COOKIE_AGE expires server-side while the user keeps browsing normally,
and the next session-authenticated request (e.g. an xblock save) fails
(fccn/nau-technical#1036).

Debounced (touches the session at most once per SESSION_TOUCH_INTERVAL_SECONDS)
rather than on every request, to avoid adding write/race pressure to the many
parallel requests Studio's frontend fires.
"""
from __future__ import absolute_import, unicode_literals

import time

SESSION_TOUCH_INTERVAL_SECONDS = 600  # well under SESSION_COOKIE_AGE (14 days)
SESSION_TOUCH_KEY = "_nau_last_touch"


class TouchSessionMiddleware:
    """Debounced session keep-alive middleware. Must sit after SessionMiddleware
    (and SafeSessionMiddleware) in MIDDLEWARE so its change to session.modified
    is seen by their response-phase processing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        session = getattr(request, "session", None)
        if session is None or session.is_empty() or session.modified:
            return response

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return response

        last_touch = session.get(SESSION_TOUCH_KEY, 0)
        now = time.time()
        if now - last_touch >= SESSION_TOUCH_INTERVAL_SECONDS:
            session[SESSION_TOUCH_KEY] = now
            session.modified = True

        return response
