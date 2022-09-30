"""Email block backend abstraction."""

from importlib import import_module

from django.conf import settings


def get_email_target():
    """ Get has_access function from edx-platform"""

    backend_module = settings.NAU_EMAIL_MODULE
    backend = import_module(backend_module)

    return backend.get_email_target()


def get_target():
    """ Get has_access function from edx-platform"""

    backend_module = settings.NAU_EMAIL_MODULE
    backend = import_module(backend_module)

    return backend.get_target()


EMAIL_TARGETS = get_email_target()
Target = get_target()
