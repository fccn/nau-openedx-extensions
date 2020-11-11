# -*- coding: utf-8 -*-
""" Configuration as explained on tutorial
github.com/edx/edx-platform/tree/master/openedx/core/djangoapps/plugins"""
from __future__ import absolute_import, unicode_literals

from django.apps import AppConfig


class NauOpenCmsConfig(AppConfig):
    """Studio configuration"""

    name = "nau_openedx_extensions.studio"
    verbose_name = "NAU openedX extensions for studio"
    plugin_app = {
        "settings_config": {
            'cms.djangoapp': {
                'common': {'relative_path': 'settings.common'},
                'test': {'relative_path': 'settings.test'},
                "production": {"relative_path": "settings.production"},
            },
        },
    }
