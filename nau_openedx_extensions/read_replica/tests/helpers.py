"""
Helpers shared by the read replica routing tests.
"""
from contextlib import contextmanager
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import router


@contextmanager
def replica_configured():
    """
    Pretend the ``read_replica`` alias exists, as it does in the NAU deployments.

    The router only checks that the alias is in ``DATABASES`` and never opens a connection to pick a database.
    """
    with patch.dict(settings.DATABASES, {"read_replica": settings.DATABASES["default"]}):
        yield


def routed_read_database():
    """
    Return the database the router picks, right now, for a read of an ordinary model.
    """
    return router.db_for_read(get_user_model())
