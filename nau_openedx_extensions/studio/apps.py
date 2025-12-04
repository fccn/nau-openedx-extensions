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
        Method to perform actions after apps registry is ended
        """
        print("Starting NAU Open edX Extensions Studio app...")
        
        # Monkey-patch will be applied via middleware on first request
        # to avoid circular import during Django initialization
        
        # Verify our custom handler exists
        try:
            from nau_openedx_extensions.studio.contentstore.video_storage_handlers import storage_service_bucket
            print("NAU: Custom storage_service_bucket loaded successfully")
            print(f"NAU: Handler module: {storage_service_bucket.__module__}")
        except ImportError as e:
            print(f"NAU: Warning - custom storage_service_bucket not found: {e}")
        
        print("NAU Open edX Extensions Studio app started.")
        print("NAU: Video storage handler will be patched on first HTTP request")
