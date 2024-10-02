"""
Student backend abstraction
"""
from __future__ import absolute_import, unicode_literals

from importlib import import_module

from django.conf import settings


def get_user_id_verifications(user_id, *args, **kwargs):
    """
    Read the user's `ManualVerification` from the edx-platform.
    """

    backend_module = settings.NAU_VERIFY_STUDENT_MODULE
    backend = import_module(backend_module)

    return backend.get_user_id_verifications(user_id, *args, **kwargs)


def create_user_id_verification(user_id, *args, **kwargs):
    """
    Create an user Id Verification `ManualVerification` instance on the edx-platform.
    """
    backend_module = settings.NAU_VERIFY_STUDENT_MODULE
    backend = import_module(backend_module)

    return backend.create_user_id_verification(user_id, *args, **kwargs)
