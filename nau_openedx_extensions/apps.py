# -*- coding: utf-8 -*-
""" Configuration as explained on tutorial
github.com/edx/edx-platform/tree/master/openedx/core/djangoapps/plugins"""
from __future__ import absolute_import, unicode_literals

from django.apps import AppConfig


class NauOpenEdxConfig(AppConfig):
    """App configuration"""

    name = "nau_openedx_extensions"
    verbose_name = "NAU openedX extensions"
    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "nau-openedx-extensions",
                "regex": r"^nau-openedx-extensions/",
                "relative_path": "urls",
            },
        },
        "settings_config": {
            "lms.djangoapp": {
                "test": {"relative_path": "settings.test"},
                "common": {"relative_path": "settings.common"},
                "production": {"relative_path": "settings.production"},
            },
            'cms.djangoapp': {
                'common': {'relative_path': 'settings.common'},
                'test': {'relative_path': 'settings.test'},
                "production": {"relative_path": "settings.production"},
            },
        },
    }

    def ready(self):
        """
        Method to perform actions after apps registry is ended
        """
        from nau_openedx_extensions.permissions import load_permissions

        #load_permissions()
