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
                'production': {'relative_path': 'settings.production'},
            },
        },
    }

    def ready(self):
        """
        Connect CMS signal handlers once the app registry is ready.
        """
        from nau_openedx_extensions.course_filters.handlers import (  # pylint: disable=import-outside-toplevel
            course_published_handler,
        )
        from xmodule.modulestore.django import SignalHandler  # pylint: disable=import-error,import-outside-toplevel

        SignalHandler.course_published.connect(course_published_handler)
