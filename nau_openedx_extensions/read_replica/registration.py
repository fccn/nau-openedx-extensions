"""
Installing the GET routing into the LMS settings.

This runs from the production plugin settings, after ``ENV_TOKENS`` is loaded and before Tutor's generated settings
run, so the router is replaced in place: the entries around it, which Tutor removes by name, stay where they are.
Only strings are used here, because the router and the middleware must not be imported while settings load.
"""
import logging

log = logging.getLogger(__name__)

UPSTREAM_ROUTER = "edx_django_utils.db.read_replica.ReadReplicaRouter"
NAU_ROUTER = "nau_openedx_extensions.read_replica.router.NauReadReplicaRouter"
MIDDLEWARE = "nau_openedx_extensions.read_replica.middleware.NauReadReplicaMiddleware"
# The platform keeps this one near the end ("This must be last"). The middleware goes right before it. Some
# platform settings, like the third party auth ones, append their own middleware after it.
LAST_MIDDLEWARE = "openedx.core.djangoapps.site_configuration.middleware.SessionCookieDomainOverrideMiddleware"


def register_get_routing(settings):
    """
    Replace the upstream read replica router with the NAU one and add the middleware.

    The decision is made on the router, not on ``SERVICE_VARIANT``, which is only set by an environment variable:
    the LMS registers ``ReadReplicaRouter`` and the Studio does not, so there is nothing to extend in the Studio.
    Safe to call twice.
    """
    routers = settings.DATABASE_ROUTERS
    if UPSTREAM_ROUTER in routers:
        routers[routers.index(UPSTREAM_ROUTER)] = NAU_ROUTER
    elif NAU_ROUTER not in routers:
        log.warning("%s is not in DATABASE_ROUTERS, the read replica GET routing is not installed.", UPSTREAM_ROUTER)
        return

    middleware = settings.MIDDLEWARE
    if MIDDLEWARE not in middleware:
        position = middleware.index(LAST_MIDDLEWARE) if LAST_MIDDLEWARE in middleware else len(middleware)
        middleware.insert(position, MIDDLEWARE)
