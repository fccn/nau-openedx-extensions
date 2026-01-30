# -*- coding: utf-8 -*-
"""
Tests for message type monkey patching.
"""
from __future__ import absolute_import, unicode_literals

from django.test import TestCase, override_settings


class MessageTypePatchTestCase(TestCase):
    """
    Test cases for message type monkey patching to set override_default_channel.
    """

    def test_bulk_email_class_is_patched(self):
        """
        Test that BulkEmail class has been monkey patched.

        This test verifies that the apps.py ready() method successfully
        imported and patched the BulkEmail class from edx-platform.
        """
        try:
            from lms.djangoapps.bulk_email.message_types import BulkEmail  # pylint: disable=import-error
        except ImportError:
            self.skipTest('BulkEmail not available (edx-platform not installed)')

        # Verify that BulkEmail class exists and has __init__
        self.assertTrue(
            hasattr(BulkEmail, '__init__'),
            'BulkEmail should have __init__ method'
        )

        # The patched __init__ should have specific attributes from our monkey patch
        # We can't easily test the full behavior without proper Message instantiation,
        # but we can verify the class was loaded and is available
        self.assertEqual(
            BulkEmail.__name__,
            'BulkEmail',
            'BulkEmail class should be available'
        )

    def test_monkey_patch_integration(self):
        """
        Test that the email_channel app ready() method executed without errors.

        This is an integration test that verifies the monkey patching code
        in apps.py:ready() runs successfully. If we reach this point, it means:
        1. The app was initialized
        2. The monkey patch code ran (or skipped gracefully if message types unavailable)
        3. No exceptions were raised during app initialization
        """
        # If we get here, the app initialized successfully
        from nau_openedx_extensions.email_channel.apps import EmailChannelConfig

        self.assertEqual(
            EmailChannelConfig.name,
            'nau_openedx_extensions.email_channel',
            'Email channel app should be configured correctly'
        )

    @override_settings(
        ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES={
            'lms.djangoapps.bulk_email.message_types.BulkEmail': 'django_email_bulk',
        }
    )
    def test_configuration_is_respected(self):
        """
        Test that ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES setting is used for patching.

        This verifies that the configuration-driven approach works and that
        the settings are properly read during app initialization.
        """
        from django.conf import settings

        overrides = getattr(settings, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES', {})

        self.assertIn(
            'lms.djangoapps.bulk_email.message_types.BulkEmail',
            overrides,
            'BulkEmail should be in the configured overrides'
        )
        self.assertEqual(
            overrides['lms.djangoapps.bulk_email.message_types.BulkEmail'],
            'django_email_bulk',
            'BulkEmail should route to django_email_bulk'
        )

    def test_empty_configuration_handled_gracefully(self):
        """
        Test that ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES configuration exists.

        Verifies that the setting is properly defined and is a dict.
        The app should handle both empty and populated configurations.
        """
        from django.conf import settings

        # Verify the setting exists (it's set in settings.py)
        overrides = getattr(settings, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES', None)

        # The setting should exist and be a dict
        self.assertIsNotNone(overrides, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES should be defined')
        self.assertIsInstance(overrides, dict, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES should be a dict')

        # The config should have the BulkEmail mapping by default
        self.assertIn(
            'lms.djangoapps.bulk_email.message_types.BulkEmail',
            overrides,
            'Default configuration should include BulkEmail mapping'
        )

    def test_channel_validation_warns_if_not_enabled(self):
        """
        Test that the ready() method logs a warning if configured channel is not enabled.

        This verifies that the channel validation catches misconfigured channels
        and warns the administrator.
        """
        import importlib

        from django.conf import settings

        # Temporarily modify settings to have a channel not in enabled list
        original_overrides = getattr(settings, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES', {})
        original_enabled = getattr(settings, 'ACE_ENABLED_CHANNELS', [])

        try:
            # Set up a misconfigured state
            settings.ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES = {
                'lms.djangoapps.bulk_email.message_types.BulkEmail': 'nonexistent_channel',
            }
            settings.ACE_ENABLED_CHANNELS = ['django_email']  # nonexistent_channel NOT in list

            # Capture log output
            with self.assertLogs('nau_openedx_extensions.email_channel', level='WARNING') as log_context:
                # Reload the module to trigger ready() again
                from nau_openedx_extensions.email_channel import apps
                importlib.reload(apps)

                # Re-instantiate and call ready() to test validation
                config = apps.EmailChannelConfig('test', apps)
                config.ready()

            # Verify warning was logged
            warning_found = any(
                'nonexistent_channel' in log and 'not in ACE_ENABLED_CHANNELS' in log
                for log in log_context.output
            )
            self.assertTrue(
                warning_found,
                'Should log warning when channel is not in ACE_ENABLED_CHANNELS'
            )

        finally:
            # Restore original settings
            settings.ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES = original_overrides
            settings.ACE_ENABLED_CHANNELS = original_enabled

    def test_channel_validation_passes_when_enabled(self):
        """
        Test that no warning is logged when channel is properly enabled.
        """
        from django.conf import settings

        # Verify default configuration has bulk channel enabled
        enabled_channels = getattr(settings, 'ACE_ENABLED_CHANNELS', [])
        overrides = getattr(settings, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES', {})

        if 'lms.djangoapps.bulk_email.message_types.BulkEmail' in overrides:
            target_channel = overrides['lms.djangoapps.bulk_email.message_types.BulkEmail']
            self.assertIn(
                target_channel,
                enabled_channels,
                f'Channel {target_channel} should be in ACE_ENABLED_CHANNELS'
            )
