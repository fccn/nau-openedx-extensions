"""
Settings for nau_openedx_extensions
"""

from __future__ import absolute_import, unicode_literals


def plugin_settings(settings):
    """
    Defines seb_openedx settings when app is used as a plugin to edx-platform.
    See: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """

    settings.NOX_CUSTOM_SAML_IDENTITY_PROVIDERS = getattr(settings, 'ENV_TOKENS', {}).get(
        'NOX_CUSTOM_SAML_IDENTITY_PROVIDERS',
        settings.NOX_CUSTOM_SAML_IDENTITY_PROVIDERS
    )
    settings.NOX_ADD_SAML_IDP_CHOICES = getattr(settings, 'ENV_TOKENS', {}).get(
        'NOX_ADD_SAML_IDP_CHOICES',
        settings.NOX_ADD_SAML_IDP_CHOICES
    )
    settings.NOX_ADD_SAML_IDP_CLASSES = getattr(settings, 'ENV_TOKENS', {}).get(
        'NOX_ADD_SAML_IDP_CLASSES',
        settings.NOX_ADD_SAML_IDP_CLASSES
    )
    settings.NOX_APPLY_SAML_OVERRIDES = getattr(settings, 'ENV_TOKENS', {}).get(
        'NOX_APPLY_SAML_OVERRIDES',
        settings.NOX_APPLY_SAML_OVERRIDES
    )
    settings.NOX_CERTIFICATE_CONTEXT_EXTENSION = getattr(settings, 'ENV_TOKENS', {}).get(
        'NOX_CERTIFICATE_CONTEXT_EXTENSION',
        settings.NOX_CERTIFICATE_CONTEXT_EXTENSION
    )
    settings.NOX_REGISTRATION_MODULE = getattr(settings, 'ENV_TOKENS', {}).get(
        'NOX_REGISTRATION_MODULE',
        settings.NOX_REGISTRATION_MODULE
    )
    settings.NOX_GRADES_MODULE = getattr(settings, 'ENV_TOKENS', {}).get(
        'NOX_GRADES_MODULE',
        settings.NOX_GRADES_MODULE
    )
