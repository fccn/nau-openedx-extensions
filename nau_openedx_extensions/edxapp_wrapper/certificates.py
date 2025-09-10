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


def get_certificate_html_view_configuration_class():
    """
    Wrapper for `lms.djangoapps.certificates.models.CertificateHtmlViewConfiguration` in edx-platform.
    """
    backend_function = settings.NAU_CERTIFICATES_MODULE
    backend = import_module(backend_function)
    return backend.CertificateHtmlViewConfiguration


def get_catalog_data_for_course(*args, **kwargs):
    """
    Wrapper for `lms.djangoapps.certificates.views.webview._get_catalog_data_for_course` in edx-platform.
    """
    backend_function = settings.NAU_CERTIFICATES_MODULE
    backend = import_module(backend_function)
    return backend._get_catalog_data_for_course(*args, **kwargs)  # pylint: disable=protected-access


def get_custom_template_and_language(*args, **kwargs):
    """
    Wrapper for `lms.djangoapps.certificates.views.webview._get_custom_template_and_language` in edx-platform.
    """
    backend_function = settings.NAU_CERTIFICATES_MODULE
    backend = import_module(backend_function)
    return backend._get_custom_template_and_language(*args, **kwargs)  # pylint: disable=protected-access


GeneratedCertificate = get_generated_certificate_class()
CertificateHtmlViewConfiguration = get_certificate_html_view_configuration_class()
