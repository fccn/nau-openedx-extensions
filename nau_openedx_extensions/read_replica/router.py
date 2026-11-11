"""
The database router of the read replica routing.
"""
import logging

from edx_django_utils.db.read_replica import READ_REPLICA_NAME, WRITER_NAME, ReadReplicaRouter

from nau_openedx_extensions.read_replica.state import request_state

log = logging.getLogger(__name__)


class NauReadReplicaRouter(ReadReplicaRouter):
    """
    ``ReadReplicaRouter`` that goes back to the writer once the request has written.

    Without a ``read_queries_only()`` block it behaves exactly like the upstream router, so registering it
    changes nothing until a request or a task opens one.

    A request that reads a row from the replica and then writes it back with ``save()`` would write the whole
    row, including columns that are a few milliseconds stale. Django's own read-modify-write helpers
    (``get_or_create``, ``update_or_create``, ``select_for_update``) already read from the writer. For the rest the
    router cannot stop the save, but it logs it, so an endpoint that does it can be taken off the allow-list.
    """

    def db_for_read(self, model, **hints):
        if request_state.wrote:
            return WRITER_NAME
        return super().db_for_read(model, **hints)

    def db_for_write(self, model, **hints):
        instance = hints.get("instance")
        if request_state.active and getattr(getattr(instance, "_state", None), "db", None) == READ_REPLICA_NAME:
            log.warning(
                "A %s loaded from the read replica is being saved (path=%s): the endpoint is not read only.",
                model._meta.label,  # pylint: disable=protected-access
                request_state.path,
            )
        return super().db_for_write(model, **hints)
