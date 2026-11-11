"""
The context manager that sends reads to the read replica.
"""
import logging
from contextlib import ExitStack, contextmanager

from edx_django_utils.db.read_replica import read_queries_only

log = logging.getLogger(__name__)


@contextmanager
def replica_reads():
    """
    Send every read made inside the block to the read replica. Writes still go to the writer.

    This is ``read_queries_only()`` with one difference: if it cannot be entered, the block runs with the default
    routing (the writer) instead of failing. ``read_queries_only()`` refuses to run inside a ``write_queries()``
    block, and a slow report is not worth failing for an optimisation. Only the entering is protected, an error
    raised by the block itself is never swallowed.

    The upstream router only reads the replica when ``read_replica`` is in ``DATABASES`` and otherwise keeps the
    writer, so this is also a no-op in environments without a replica.
    """
    with ExitStack() as stack:
        try:
            stack.enter_context(read_queries_only())
        except AssertionError:
            log.warning("Cannot route reads to the replica inside write_queries(), using the writer.")
        yield
