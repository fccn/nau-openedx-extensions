"""
Helpers shared by the read replica routing tests.
"""
from contextlib import contextmanager
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connections, router


@contextmanager
def replica_configured():
    """
    Pretend the ``read_replica`` alias exists, as it does in the NAU deployments.

    The router only checks that the alias is in ``DATABASES`` and never opens a connection to pick a database.
    If a test really reads through the alias, it gets the connection of the writer: the tests run on an in-memory
    SQLite database, where a second connection would be locked out by the first one's open transaction.
    """
    with patch.dict(settings.DATABASES, {"read_replica": settings.DATABASES["default"]}):
        connections["read_replica"] = connections["default"]
        try:
            yield
        finally:
            del connections["read_replica"]


def routed_read_database():
    """
    Return the database the router picks, right now, for a read of an ordinary model.
    """
    return router.db_for_read(get_user_model())
