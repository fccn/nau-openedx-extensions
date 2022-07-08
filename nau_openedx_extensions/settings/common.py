"""
Settings for nau_openedx_extensions
"""

from __future__ import absolute_import, unicode_literals

SECRET_KEY = "a-not-to-be-trusted-secret-key"
INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "nau_openedx_extensions",
)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


def plugin_settings(settings):
    """
    Defines seb_openedx settings when app is used as a plugin to edx-platform.
    See: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """

    settings.NAU_CUSTOM_SAML_IDENTITY_PROVIDERS = [
        {
            "provider_key": "nau_custom_saml_provider",
            "provider_class": "nau_openedx_extensions.third_party_auth.providers.saml.NauEdXSAMLIdentityProvider",
            "verbose_name": "NAU SAML provider",
        }
    ]

    settings.NAU_ADD_SAML_IDP_CHOICES = "nau_openedx_extensions.third_party_auth.providers.saml.get_extended_saml_idp_choices"
    settings.NAU_ADD_SAML_IDP_CLASSES = (
        "nau_openedx_extensions.third_party_auth.providers.saml.extend_saml_idp_classes"
    )
    settings.NAU_APPLY_SAML_OVERRIDES = (
        "nau_openedx_extensions.third_party_auth.providers.saml._apply_saml_overrides"
    )
    settings.NAU_CERTIFICATE_CONTEXT_EXTENSION = (
        "nau_openedx_extensions.certificates.context_extender.update_cert_context"
    )
    settings.NAU_STUDENT_ACCOUNT_CONTEXT_EXTENSION = "nau_openedx_extensions.custom_registration_form.context_extender.update_account_view"
    settings.NAU_STUDENT_SERIALIZER_CONTEXT_EXTENSION = "nau_openedx_extensions.custom_registration_form.context_extender.update_account_serializer"
    settings.NAU_STUDENT_ACCOUNT_PARTIAL_UPDATE = "nau_openedx_extensions.custom_registration_form.context_extender.partial_update"
    settings.NAU_COURSEWARE_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.courseware_h_v1"
    )
    settings.NAU_FRAGMENTS_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.fragments_h_v1"
    )
    settings.NAU_GRADES_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.grades_h_v1"
    )
    settings.NAU_REGISTRATION_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.registration_l_v1"
    )
    settings.NAU_COURSE_MESSAGE_BATCH_SIZE = 50
    settings.NAU_COURSE_MESSAGE_RECIPIENT_FIELDS = ["profile__name", "email"]
    settings.NAU_CC_ALLOWED_SLUG = "cccmd:"
    settings.NAU_ACCOUNTS_CC_VISIBLE_FIELDS = ["employment_situation", "nif"]
    settings.SCORMXBLOCK_ASYNC_THRESHOLD = 500
