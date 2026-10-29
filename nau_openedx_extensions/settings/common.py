"""
Settings for nau_openedx_extensions
"""

from __future__ import absolute_import, unicode_literals

from django.utils.translation import gettext_lazy as _

from nau_openedx_extensions import ROOT_DIRECTORY

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

    # Overwrite the default certificate name
    settings.CERT_NAME_SHORT = _("Certificate")
    settings.CERT_NAME_LONG = _("Certificate of Achievement")

    settings.MAKO_TEMPLATE_DIRS_BASE.append(ROOT_DIRECTORY / "templates")

    settings.NAU_CERTIFICATE_CONTEXT_EXTENSION = (
        "nau_openedx_extensions.certificates.context_extender.update_cert_context"
    )
    settings.NAU_STUDENT_ACCOUNT_CONTEXT_EXTENSION = (
        "nau_openedx_extensions.custom_registration_form.context_extender.update_account_view"
    )
    settings.NAU_STUDENT_SERIALIZER_CONTEXT_EXTENSION = (
        "nau_openedx_extensions.custom_registration_form.context_extender.update_account_serializer"
    )
    settings.NAU_STUDENT_ACCOUNT_PARTIAL_UPDATE = (
        "nau_openedx_extensions.custom_registration_form.context_extender.partial_update"
    )
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
    settings.NAU_COURSE_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.course_module_l_v1"
    )
    settings.NAU_EMAIL_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.email_module_l_v1"
    )
    settings.NAU_COURSE_MESSAGE_BATCH_SIZE = 50
    settings.NAU_COURSE_MESSAGE_RECIPIENT_FIELDS = ["profile__name", "email"]
    settings.NAU_CC_ALLOWED_SLUG = "cccmd:"
    settings.NAU_ACCOUNTS_CC_VISIBLE_FIELDS = [
        "employment_situation",
        "nif",
        "allow_newsletter",
        "nuts",
        "cae4",
    ]

    # Global allowlist of all User attribute names that may ever be appended to the
    # Student Profile Info CSV report via the per-course advanced setting
    # ``nau_additional_features_on_instructor_analytics_student_profile_info``
    # (fccn/nau-technical#797). Only fields present here will be accepted; any other
    # field requested at the course level will be skipped with a warning.
    #
    # Example::
    #
    #   NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO = [
    #       "nau_nif",
    #       "nau_user_extended_model_cc_nic",
    #   ]
    settings.NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO = []

    # fccn/nau-technical#1036: keep the plain CMS session alive for users who are
    # only making JWT-authenticated requests (e.g. via the authoring MFE), which
    # never otherwise touch/resave it. See studio.session_refresh for details.
    if settings.SERVICE_VARIANT == "cms":
        middleware = "nau_openedx_extensions.studio.session_refresh.TouchSessionMiddleware"
        if middleware not in settings.MIDDLEWARE:
            settings.MIDDLEWARE.append(middleware)

    settings.SCORMXBLOCK_ASYNC_THRESHOLD = 500
    settings.NAU_SITE_CONFIGURATION_HELPERS_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.site_configuration_helpers_l_v1"
    )
    settings.NAU_STUDENT_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.student_l_v1"
    )
    settings.NAU_COHORT_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.cohort_v1"
    )
    settings.NAU_VERIFY_STUDENT_MODULE = (
        "nau_openedx_extensions.edxapp_wrapper.backends.verify_student_v1"
    )
    settings.NAU_CERTIFICATES_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.certificates_r_v1"
    settings.NAU_UTIL_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.util_r_v1"
    settings.NAU_INSTRUCTOR_TASK_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.instructor_task_r_v1"
    settings.NAU_SITE_CONFIGURATION_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.site_configuration_r_v1"
    settings.NAU_CONTENT_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.content_r_v1"

    # Phase 2 report identity columns (fccn/nau-technical#955): when enabled,
    # every CSV course report is prepended with course_id and, on learner-grain
    # reports, email, username and student_id. Default off; enabling it is a
    # breaking change for consumers that read reports by column position.
    settings.NAU_REPORTS_ENABLE_BASE_COLUMNS = False

    # Use the casing of the course keys stored in the course overview (the canonical one) in the
    # requests and in the course home URLs (fccn/nau-technical#1090). Set to False to disable it.
    settings.NAU_CANONICAL_COURSE_KEYS_ENABLED = True
    middleware = "nau_openedx_extensions.canonical_course_key.middleware.CanonicalCourseKeyMiddleware"
    if middleware not in settings.MIDDLEWARE:
        settings.MIDDLEWARE.append(middleware)
    _append_filter_pipeline_step(
        settings,
        "org.openedx.learning.course.homepage.url.creation.started.v1",
        "nau_openedx_extensions.canonical_course_key.filters.CourseHomeUrlCanonicalCourseKey",
    )

    # Phase 2 certificate date (fccn/nau-technical#955, request #32): when
    # enabled, the grade report carries a final certificate_obtained_date
    # column (GeneratedCertificate.created_date for delivered certificates).
    # Default off.
    settings.NAU_REPORTS_ENABLE_CERTIFICATE_DATE = False


def _append_filter_pipeline_step(settings, filter_type, pipeline_step):
    """
    Add a pipeline step to the configuration of an Open edX filter, keeping the existing configuration.

    A filter configured here is created with `fail_silently` enabled, as the steps added by this plugin are
    best-effort, unlike the ones added with `append_filter_config` in nau-tutor-configs. The option of a filter
    that is already configured is kept.
    """
    if not hasattr(settings, "OPEN_EDX_FILTERS_CONFIG"):
        settings.OPEN_EDX_FILTERS_CONFIG = {}
    filter_config = settings.OPEN_EDX_FILTERS_CONFIG.setdefault(
        filter_type, {"fail_silently": True, "pipeline": []}
    )
    if pipeline_step not in filter_config["pipeline"]:
        filter_config["pipeline"].append(pipeline_step)
