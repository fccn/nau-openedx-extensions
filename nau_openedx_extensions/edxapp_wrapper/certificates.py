"""
Certificate backend abstraction.
"""

from importlib import import_module

from django.conf import settings


def get_generated_certificate_class():
    """
    Wrapper for `lms.djangoapps.certificates.models.GeneratedCertificate` in edx-platform.
    """
    backend_function = settings.NAU_CERTIFICATES_MODULE
    backend = import_module(backend_function)
    return backend.GeneratedCertificate


GeneratedCertificate = get_generated_certificate_class()
