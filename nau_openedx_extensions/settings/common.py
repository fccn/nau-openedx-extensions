"""
Settings for nau_openedx_extensions
"""

from __future__ import absolute_import, unicode_literals


SECRET_KEY = 'a-not-to-be-trusted-secret-key'
INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'nau_openedx_extensions',
)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


def plugin_settings(settings):
    """
    Defines seb_openedx settings when app is used as a plugin to edx-platform.
    See: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """
    settings.CERTIFICATE_CONTEXT_EXTENSION = 'nau_openedx_extensions.certificates.update_cert_context'

    settings.CUSTOM_SAML_IDENTITY_PROVIDERS = [
        {
            "provider_key": "nau_custom_saml_provider",
            "idp_module": "nau_openedx_extensions.third_party_auth.providers.saml",
            "idp_class": "NauEdXSAMLIdentityProvider",
            "verbose_name": "NAU SAML provider"
        }
    ]
