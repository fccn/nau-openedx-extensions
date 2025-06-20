"""
Instructor views API public function definitions.
"""
from importlib import import_module

from django.conf import settings


def use_read_replica_if_available(*args, **kwargs):
    """
    Wrapper for `common.djangoapps.util.query.use_read_replica_if_available` in edx-platform.
    """
    backend_function = settings.NAU_UTIL_MODULE
    backend = import_module(backend_function)
    return backend.use_read_replica_if_available(*args, **kwargs)
