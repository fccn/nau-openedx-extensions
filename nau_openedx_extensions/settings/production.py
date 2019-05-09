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
