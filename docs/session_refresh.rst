Session keep-alive (CMS)
========================

Studio pages are mostly served through the authoring MFE, authenticated with a JWT cookie that
the MFE refreshes on its own. Saving (``xblock_handler``) and a few other views, however, are
authenticated with the plain Django session instead, which is never touched by JWT-only
requests. If a session goes untouched for ``SESSION_COOKIE_AGE`` (14 days by default) it expires
server-side while the user keeps browsing normally through the MFE, and the next save then fails:
it gets redirected into the CMS-LMS OAuth2 re-authentication dance, which a browser blocks on its
final, cross-origin step (CORS), so the save never succeeds and the automatic retry/re-login
prompt cannot complete it either (fccn/nau-technical#1036).

What it does
------------

``TouchSessionMiddleware``, in Studio only, keeps a session with its own logged-in user alive:
at most once per ``NAU_SESSION_TOUCH_INTERVAL_SECONDS``, it marks the session modified so
``SessionMiddleware``/``SafeSessionMiddleware`` resave and re-sign it on the way out. This is a
security-relevant behaviour change: a Studio session now ends ``SESSION_COOKIE_AGE`` after the
user's last activity (sliding expiration) rather than after their last login.

A session is only touched when it already has its own logged-in user (``SESSION_KEY`` in the
session) -- an authenticated ``request.user`` from a JWT-authenticated request over an otherwise
anonymous session (for instance mid SSO dance) does not count, to avoid writing to a session that
is not actually logged in. The check is debounced through an atomic cache key per session, so
several requests arriving at the same time only touch the session once, not once each.

This does not heal a session that has already expired; the user still needs one top-level
navigation to Studio to get a fresh one.

The touch re-saves the session as it was loaded at the start of the request, so a key written by
a concurrent request can still be overwritten -- at most once per interval per session, since the
debounce gate limits touches, not regular session-modifying requests. This is a design limit of
cache-backed sessions (no merge, last writer wins) and is not closed by this middleware. Accepted
because only a few CMS paths write to the session (import status, ``VIDEOS_PER_PAGE``, messages,
login/SSO, XBlock preview state).

Configuration
-------------

``NAU_SESSION_TOUCH_ENABLED``
    Default: ``True``. Set it to ``False``, for instance in the env tokens, to disable it.

``NAU_SESSION_TOUCH_INTERVAL_SECONDS``
    Default: ``600``. Clamped to ``SESSION_COOKIE_AGE // 4``, so a shorter ``SESSION_COOKIE_AGE``
    (for instance while testing) does not let a session go stale between touches. Read once at
    startup, so changing it needs a restart. Values below 1 are raised to 1. A non-numeric value
    stops the CMS from starting. ``NAU_SESSION_TOUCH_ENABLED=False`` is checked first and always
    works.
