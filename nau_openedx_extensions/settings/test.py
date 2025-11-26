"""
Settings for nau_openedx_extensions
"""
from __future__ import absolute_import, unicode_literals

from lms.envs.test import *  # pylint: disable=wildcard-import,unused-wildcard-import

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    'student_module_history': {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

# This is to avoid "initialized translation infrastructure before the apps registry is ready" issue in tests.
USE_I18N = False

# Certificate export
# HIGH_MEM_QUEUE = "edx.lms.core.high_mem"

# LMS settings for tests
LMS_ROOT_URL = "https://lms.example.com"

##############################################################################
# This override modules design has been deprecated.
# Now we are depending on the edx-platform for:
# - test settings mechanism.
# - using factories for better test data creation.
# - and use Django models from edx-platform.
#
# NAU_COURSE_MODULE = (
#     "nau_openedx_extensions.edxapp_wrapper.backends.course_module_l_v1_tests"
# )
# NAU_EMAIL_MODULE = (
#     "nau_openedx_extensions.edxapp_wrapper.backends.email_module_l_v1_tests"
# )
#
# NAU_SITE_CONFIGURATION_HELPERS_MODULE = (
#     "nau_openedx_extensions.edxapp_wrapper.backends.site_configuration_helpers_l_v1_tests"
# )
#
# NAU_STUDENT_MODULE = (
#     "nau_openedx_extensions.edxapp_wrapper.backends.student_l_v1_tests"
# )
#
# NAU_COHORT_MODULE = (
#     "nau_openedx_extensions.edxapp_wrapper.backends.cohort_v1_tests"
# )
# NAU_VERIFY_STUDENT_MODULE = (
#     "nau_openedx_extensions.edxapp_wrapper.backends.verify_student_v1_tests"
# )
# NAU_CERTIFICATES_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.certificates_r_v1_tests"
# # NAU_UTIL_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.util_r_v1_tests"
# NAU_INSTRUCTOR_TASK_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.instructor_task_r_v1_tests"
# NAU_SITE_CONFIGURATION_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.site_configuration_r_v1_tests"
# NAU_CONTENT_MODULE = "nau_openedx_extensions.edxapp_wrapper.backends.content_r_v1_tests"
#
##############################################################################

#
# Settings required for Mongo connection in tests
#
from xmodule.modulestore.modulestore_settings import \
    update_module_store_settings  # pylint: disable=wrong-import-position

# Mongodb connection parameters: simply modify `mongodb_parameters` to affect all connections to MongoDb.
mongodb_parameters = {
    "db": "openedx",
    "host": "127.0.0.1",
    "port": 27017,
    "user": None,
    "password": None,
    # Connection/Authentication
    "connect": False,
    "ssl": False,
    "authsource": "admin",
    "replicaSet": None,
}
DOC_STORE_CONFIG = mongodb_parameters
CONTENTSTORE = {
    "ENGINE": "xmodule.contentstore.mongo.MongoContentStore",
    "ADDITIONAL_OPTIONS": {},
    "DOC_STORE_CONFIG": DOC_STORE_CONFIG
}
# Load module store settings from config files
update_module_store_settings(MODULESTORE, doc_store_settings=DOC_STORE_CONFIG)
DATA_DIR = "/openedx/data/modulestore"

for store in MODULESTORE["default"]["OPTIONS"]["stores"]:
   store["OPTIONS"]["fs_root"] = DATA_DIR
