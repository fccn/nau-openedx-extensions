"""
Settings for nau_openedx_extensions
"""

from __future__ import absolute_import, unicode_literals


def plugin_settings(settings):
    """
    Defines seb_openedx settings when app is used as a plugin to edx-platform.
    See: https://github.com/edx/edx-platform/blob/master/openedx/core/djangoapps/plugins/README.rst
    """

    settings.NAU_CUSTOM_SAML_IDENTITY_PROVIDERS = getattr(
        settings, "ENV_TOKENS", {}
    ).get(
        "NAU_CUSTOM_SAML_IDENTITY_PROVIDERS",
        settings.NAU_CUSTOM_SAML_IDENTITY_PROVIDERS,
    )
    settings.NAU_ADD_SAML_IDP_CHOICES = getattr(settings, "ENV_TOKENS", {}).get(
        "NAU_ADD_SAML_IDP_CHOICES", settings.NAU_ADD_SAML_IDP_CHOICES
    )
    settings.NAU_ADD_SAML_IDP_CLASSES = getattr(settings, "ENV_TOKENS", {}).get(
        "NAU_ADD_SAML_IDP_CLASSES", settings.NAU_ADD_SAML_IDP_CLASSES
    )
    settings.NAU_APPLY_SAML_OVERRIDES = getattr(settings, "ENV_TOKENS", {}).get(
        "NAU_APPLY_SAML_OVERRIDES", settings.NAU_APPLY_SAML_OVERRIDES
    )
    settings.NAU_CERTIFICATE_CONTEXT_EXTENSION = getattr(
        settings, "ENV_TOKENS", {}
    ).get(
        "NAU_CERTIFICATE_CONTEXT_EXTENSION", settings.NAU_CERTIFICATE_CONTEXT_EXTENSION
    )
    settings.NAU_STUDENT_ACCOUNT_CONTEXT_EXTENSION = getattr(
        settings, "ENV_TOKENS", {}
    ).get(
        "NAU_STUDENT_ACCOUNT_CONTEXT_EXTENSION",
        settings.NAU_STUDENT_ACCOUNT_CONTEXT_EXTENSION,
    )
    settings.NAU_REGISTRATION_MODULE = getattr(settings, "ENV_TOKENS", {}).get(
        "NAU_REGISTRATION_MODULE", settings.NAU_REGISTRATION_MODULE
    )
    settings.NAU_GRADES_MODULE = getattr(settings, "ENV_TOKENS", {}).get(
        "NAU_GRADES_MODULE", settings.NAU_GRADES_MODULE
    )
    settings.NAU_CC_ALLOWED_SLUG = getattr(settings, "ENV_TOKENS", {}).get(
        "NAU_CC_ALLOWED_SLUG", settings.NAU_CC_ALLOWED_SLUG
    )
    SOCIAL_AUTH_TPA_SAML_PIPELINE = getattr(settings, "ENV_TOKENS", {}).get(
        "SOCIAL_AUTH_TPA_SAML_PIPELINE", None
    )
    if SOCIAL_AUTH_TPA_SAML_PIPELINE:
        settings.SOCIAL_AUTH_TPA_SAML_PIPELINE = SOCIAL_AUTH_TPA_SAML_PIPELINE
    settings.NAU_ACCOUNTS_CC_VISIBLE_FIELDS = getattr(settings, "ENV_TOKENS", {}).get(
        "NAU_ACCOUNTS_CC_VISIBLE_FIELDS", settings.NAU_ACCOUNTS_CC_VISIBLE_FIELDS
    )
    if settings.SERVICE_VARIANT == "cms":
        settings.MAX_ASSET_UPLOAD_FILE_SIZE_IN_MB = getattr(settings, "ENV_TOKENS", {}).get(
            'MAX_ASSET_UPLOAD_FILE_SIZE_IN_MB', settings.MAX_ASSET_UPLOAD_FILE_SIZE_IN_MB
        )
        settings.DEFAULT_COURSE_LANGUAGE = getattr(settings, "ENV_TOKENS", {}).get(
            "DEFAULT_COURSE_LANGUAGE", settings.DEFAULT_COURSE_LANGUAGE
        )
    elif settings.SERVICE_VARIANT == "lms":
        settings.COURSE_DISCOVERY_MEANINGS = getattr(settings, "ENV_TOKENS", {}).get("COURSE_DISCOVERY_MEANINGS", {})

    settings.ORA2_FILEUPLOAD_BACKEND = getattr(settings, "ENV_TOKENS", {}).get(
        "ORA2_FILEUPLOAD_BACKEND", "django"
    )
