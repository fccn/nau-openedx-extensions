"""
Settings for nau_openedx_extensions
"""

from __future__ import absolute_import, unicode_literals

from .common import *  # pylint: disable=wildcard-import, unused-wildcard-import


class SettingsClass(object):
    """ dummy settings class """

    pass


DEBUG = True
SETTINGS = SettingsClass()
plugin_settings(SETTINGS)
vars().update(SETTINGS.__dict__)


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
