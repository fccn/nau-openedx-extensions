"""
Make it more easy to mock the way that open edx allows to get the site configurations inside the
edxapp.
"""
from importlib import import_module

from django.conf import settings


def get_value(*args, **kwargs):
    """
    Get correct site configuration helper module.
    """

    backend_module = settings.NAU_SITE_CONFIGURATION_HELPERS_MODULE
    backend = import_module(backend_module)

    return backend.get_value(*args, **kwargs)
