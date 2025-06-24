"""
Settings for nau_openedx_extensions
"""

from __future__ import absolute_import, unicode_literals

DEBUG = True

SECRET_KEY = "test-secret-key-for-testing-only"

MAKO_TEMPLATE_DIRS_BASE = [
    "templates",
]

ROOT_URLCONF = "nau_openedx_extensions.urls"
ALLOWED_HOSTS = ["*"]

# This key needs to be defined so that the check_apps_ready passes and the
# AppRegistry is loaded
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite3",
    }
}

NAU_COURSE_MODULE = (
    "nau_openedx_extensions.edxapp_wrapper.backends.course_module_l_v1_tests"
)
NAU_EMAIL_MODULE = (
    "nau_openedx_extensions.edxapp_wrapper.backends.email_module_l_v1_tests"
)

# This is to avoid "initialized translation infrastructure before the apps registry is ready" issue in tests.
USE_I18N = False

NAU_SITE_CONFIGURATION_HELPERS_MODULE = (
    "nau_openedx_extensions.edxapp_wrapper.backends.site_configuration_helpers_l_v1_tests"
)

NAU_STUDENT_MODULE = (
    "nau_openedx_extensions.edxapp_wrapper.backends.student_l_v1_tests"
)

NAU_COHORT_MODULE = (
    "nau_openedx_extensions.edxapp_wrapper.backends.cohort_v1_tests"
)
NAU_VERIFY_STUDENT_MODULE = (
    "nau_openedx_extensions.edxapp_wrapper.backends.verify_student_v1_tests"
)
NAU_CERTIFICATES_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.certificates_r_v1_tests"
NAU_UTIL_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.util_r_v1_tests"
NAU_INSTRUCTOR_TASK_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.instructor_task_r_v1_tests"
NAU_SITE_CONFIGURATION_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.site_configuration_r_v1_tests"
