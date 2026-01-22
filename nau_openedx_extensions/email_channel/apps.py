# -*- coding: utf-8 -*-
"""
App configuration for email_channel module
"""
from __future__ import absolute_import, unicode_literals

from django.apps import AppConfig


class EmailChannelConfig(AppConfig):
    """
    Configuration for the email_channel application.

    This app provides custom ACE (Advanced Communication Engine) channels
    for sending emails through different SMTP relays.
    """

    name = 'nau_openedx_extensions.email_channel'
    verbose_name = 'NAU Email Channel'
    plugin_app = {
        'settings_config': {
            'lms.djangoapp': {
                'common': {'relative_path': 'settings.settings'},
            },
            'cms.djangoapp': {
                'common': {'relative_path': 'settings.settings'},
            }
        },
    }

    def ready(self):
        """
        Perform initialization when the app is ready.
        """
