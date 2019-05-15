"""
Settings for nau_openedx_extensions
"""

from __future__ import absolute_import, unicode_literals


def plugin_settings(settings):
    """
    Defines seb_openedx settings when app is used as a plugin to edx-platform.
    See: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """

    settings.CUSTOM_SAML_IDENTITY_PROVIDERS = getattr(settings, 'ENV_TOKENS', {}).get(
        'CUSTOM_SAML_IDENTITY_PROVIDERS',
        settings.CUSTOM_SAML_IDENTITY_PROVIDERS
    )
    settings.ADD_SAML_IDP_CHOICES = getattr(settings, 'ENV_TOKENS', {}).get(
        'ADD_SAML_IDP_CHOICES',
        settings.ADD_SAML_IDP_CHOICES
    )
    settings.ADD_SAML_IDP_CLASSES = getattr(settings, 'ENV_TOKENS', {}).get(
        'ADD_SAML_IDP_CLASSES',
        settings.ADD_SAML_IDP_CLASSES
    )
    settings.APPLY_SAML_OVERRIDES = getattr(settings, 'ENV_TOKENS', {}).get(
        'APPLY_SAML_OVERRIDES',
        settings.APPLY_SAML_OVERRIDES
    )
    settings.CERTIFICATE_CONTEXT_EXTENSION = getattr(settings, 'ENV_TOKENS', {}).get(
        'CERTIFICATE_CONTEXT_EXTENSION',
        settings.CERTIFICATE_CONTEXT_EXTENSION
    )
    settings.REGISTRATION_MODULE = getattr(settings, 'ENV_TOKENS', {}).get(
        'REGISTRATION_MODULE',
        settings.REGISTRATION_MODULE
    )
