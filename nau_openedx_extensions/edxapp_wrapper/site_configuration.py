"""
Site Configuration module generalized definitions.
"""

from importlib import import_module

from django.conf import settings


def get_site_configuration_model():
    """
    Wrapper for `openedx.core.djangoapps.site_configuration.models.SiteConfiguration` function in edx-platform.
    """
    backend_function = settings.NAU_SITE_CONFIGURATION_MODULE
    backend = import_module(backend_function)
    return backend.SiteConfiguration


SiteConfiguration = get_site_configuration_model()
