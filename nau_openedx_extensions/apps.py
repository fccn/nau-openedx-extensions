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
        "view_context_config": {
            "lms.djangoapp":  {
                "course_dashboard": "nau_openedx_extensions.multi_dashboard.context_processor.get_multi_dashboard_context"  # lint-amnesty, pylint: disable=line-too-long # noqa
            },
        },
    }

    def ready(self):
        """
        Method to perform actions after apps registry is ended
        """
        from nau_openedx_extensions import signals  # pylint: disable=import-outside-toplevel,unused-import # noqa
        from nau_openedx_extensions.permissions import \
            load_permissions  # pylint: disable=import-outside-toplevel,unused-import # noqa
