"""
Serve an allow-list of GET requests from the read replica.

A request is routed only if it is a GET or HEAD, its path matches ``NAU_READ_REPLICA_GET_ALLOWLIST`` and the
``nau_read_replica.get_routing`` waffle switch is active. A routed request goes through three steps:

1. **Causal barrier.** The replica applies the writes of the cluster asynchronously, so before the view runs the
   request waits until the replica has applied everything the cluster had committed at that moment. That gives
   read-your-writes to every client (browsers, MFEs, mobile apps with bearer tokens, server to server calls),
   which a cookie or a "was there a POST recently" rule cannot. It costs one round trip when the replica keeps up, and
   as much as the replication lag when it does not. If the barrier fails or times out the request is served by the
   writer, and a circuit breaker then skips the replica for a few seconds so the next requests do not pay the wait.
2. **Reads from the replica.** The view runs inside ``read_queries_only()``.
3. **Back to the writer on the first write.** Many GET endpoints write now and then (user activity, last seen
   timezone, first visit of the day). The first INSERT/UPDATE/DELETE/REPLACE or locking read sent to the writer
   moves the rest of the request to the writer too, so it never reads a row it has just changed from a replica
   that may not have it yet.

The middleware sits next to the end of the LMS middleware list, so the earlier ones (session, authentication,
language, ...) keep reading from the writer. Streaming responses are produced after the middleware returns, so
they read from the writer too.
"""
import logging
import time

from django.db import Error, connections
from django.utils.connection import ConnectionDoesNotExist
from edx_django_utils.monitoring import set_custom_attribute

from nau_openedx_extensions.read_replica import conf
from nau_openedx_extensions.read_replica.breaker import replica_breaker
from nau_openedx_extensions.read_replica.context import replica_reads
from nau_openedx_extensions.read_replica.state import request_state
from nau_openedx_extensions.read_replica.switches import GET_ROUTING
from nau_openedx_extensions.read_replica.writes import WriteDetector

log = logging.getLogger(__name__)

ROUTE_HEADER = "X-NAU-DB-Route"
REPLICA = "replica"
WRITER = "writer"


def _causal_barrier():
    """
    Wait until the read replica has applied every write the cluster committed before this call, and return how
    long that took, in seconds, without counting the time spent connecting.

    ``wsrep_sync_wait = 1`` makes the node hold a statement until it is in sync with the cluster, so a statement
    that reads no table is enough. It is set only around that statement, because the same connection then serves
    every other query of the request, and each of them would pay the wait (20 times slower on the lab when the
    replica lagged). The reset is in a ``finally``: after a timeout the variable would otherwise stay on and the
    next statement would time out too.

    The barrier must run before the view starts. The causal check is skipped for a statement that runs after a
    table was read in an open transaction, so a barrier inside the ``ATOMIC_REQUESTS`` transaction of the view
    would silently do nothing. Set ``repl.causal_read_timeout`` on the read node to about one second, otherwise a
    node that cannot catch up holds the request for thirty.
    """
    connection = connections["read_replica"]
    try:
        connection.ensure_connection()
        started = time.monotonic()
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION wsrep_sync_wait = 1")
            try:
                cursor.execute("SELECT 1")
            finally:
                cursor.execute("SET SESSION wsrep_sync_wait = 0")
        return time.monotonic() - started
    except Exception:
        # Do not leave a half used connection, possibly with the wait still on, for the rest of the request.
        connection.close()
        raise


class NauReadReplicaMiddleware:
    """
    See the module documentation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._is_routable(request):
            return self.get_response(request)

        if not self._barrier_passes():
            return self._tagged(self.get_response(request), WRITER)

        request_state.active, request_state.wrote, request_state.path = True, False, request.path
        try:
            with connections["default"].execute_wrapper(WriteDetector(request_state)), replica_reads():
                response = self.get_response(request)
            route = WRITER if request_state.wrote else REPLICA
        finally:
            request_state.reset()
        set_custom_attribute("nau_read_replica", "writer_after_write" if route == WRITER else "replica")
        return self._tagged(response, route)

    @staticmethod
    def _is_routable(request):
        """
        Return whether this request is served from the replica. The cheap checks come first, the switch last.
        """
        return bool(
            request.method in ("GET", "HEAD")
            and conf.routing_enabled()
            and conf.get_is_allowed(request.path_info)
            and GET_ROUTING.is_enabled()
        )

    @staticmethod
    def _barrier_passes():
        """
        Run the causal barrier. Return False if the replica cannot be used for this request.

        A failed or slow barrier opens the circuit breaker, so the next requests of this process skip the replica
        instead of each waiting for it. A slow barrier that did finish still passes: this request is consistent.
        """
        if replica_breaker.is_open():
            set_custom_attribute("nau_read_replica", "breaker_open")
            return False
        try:
            waited = _causal_barrier()
        except (Error, ConnectionDoesNotExist) as exc:
            replica_breaker.trip(conf.breaker_seconds())
            set_custom_attribute("nau_read_replica", "barrier_failed")
            log.warning(
                "The read replica did not pass the causal barrier, serving from the writer for the next %s s: %s",
                conf.breaker_seconds(),
                exc,
            )
            return False
        if waited * 1000 > conf.barrier_slow_ms():
            replica_breaker.trip(conf.breaker_seconds())
            log.warning(
                "The read replica needed %.0f ms to catch up, serving from the writer for the next %s s.",
                waited * 1000,
                conf.breaker_seconds(),
            )
        return True

    @staticmethod
    def _tagged(response, route):
        """
        Say where the request was served, if the debug header is on.
        """
        if conf.debug_header_enabled():
            response[ROUTE_HEADER] = route
        return response
