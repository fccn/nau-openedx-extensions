# -*- coding: utf-8 -*-
"""
App configuration for email_channel module
"""
from __future__ import absolute_import, unicode_literals

from django.apps import AppConfig


class EmailChannelConfig(AppConfig):
    """
    Configuration for the email_channel application.

    This app provides:
    - Custom ACE (Advanced Communication Engine) channels for sending emails
      through different SMTP relays
    - Automatic message type routing via monkey patching
    - Configuration-driven channel selection

    Features:
        - DjangoEmailBulkChannel: Custom channel using bulk email settings
        - Automatic BulkEmail routing to separate SMTP relay
        - Easily extensible to support additional message types

    How It Works:
        1. On app initialization, reads ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES setting
        2. Dynamically imports each configured message type class
        3. Monkey patches the __init__ method to set override_default_channel
        4. ACE automatically routes messages to the specified channel

    Adding New Message Types:
        To route additional message types to specific channels:

        1. Update settings (lms.env.json or Django settings):
           ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES = {
               'lms.djangoapps.bulk_email.message_types.BulkEmail': 'django_email_bulk',
               'lms.djangoapps.verify_student.messages.VerificationReminder': 'django_email_transactional',
           }

        2. Ensure target channel is enabled:
           ACE_ENABLED_CHANNELS = ['django_email', 'django_email_bulk', 'django_email_transactional']

        3. Create custom channel if needed (see django_email_bulk.py for example)

        4. Register channel in setup.py:
           "openedx.ace.channel": [
               "django_email_transactional = your.module:YourChannelClass",
           ]

        5. Restart services

    No code changes to apps.py required - just configuration!

    Debugging:
        Enable debug logging to see patching in action:
        LOGGING = {
            'loggers': {
                'nau_openedx_extensions.email_channel': {'level': 'DEBUG'},
            },
        }

    Error Handling:
        If a message type can't be imported/patched, a warning is logged and
        the system continues. That message type will use default channel routing.
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

        Monkey patches message types from edx-platform to automatically route them
        to specific ACE channels by setting the override_default_channel option.

        Configuration:
            ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES (dict): Maps message type paths to channel names.
                Format: {'full.module.path.ClassName': 'channel_name'}

                Example:
                    {
                        'lms.djangoapps.bulk_email.message_types.BulkEmail': 'django_email_bulk',
                        'lms.djangoapps.verify_student.messages.VerificationReminder': 'django_email_transactional',
                    }

        Process:
            1. Reads ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES from settings
            2. For each entry:
               a. Dynamically imports the message type class
               b. Wraps the __init__ method to add override_default_channel
               c. Logs success or warning
            3. Returns silently if no overrides configured

        The monkey patch adds this to each message instance:
            self.options['override_default_channel'] = 'target_channel'

        ACE then uses this to route the message to the specified channel
        instead of using the default channel selection logic.

        Notes:
            - Import errors are logged but don't crash the app
            - Uses factory function to avoid closure issues
            - Each message type can only route to one channel
        """
        import logging

        from django.conf import settings

        logger = logging.getLogger(__name__)
        logger.debug('EmailChannelConfig.ready() - email_channel app initialized')

        # Get message type routing configuration
        message_type_overrides = getattr(settings, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES', {})

        if not message_type_overrides:
            logger.info('No ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES configured, skipping message type patching')
            return

        # Get enabled channels for validation
        enabled_channels = getattr(settings, 'ACE_ENABLED_CHANNELS', [])

        # Patch each configured message type
        patched_count = 0
        for message_type_path, channel_name in message_type_overrides.items():
            try:
                # Parse the module path and class name
                module_path, class_name = message_type_path.rsplit('.', 1)

                # Validate that the target channel is enabled before patching
                if enabled_channels and channel_name not in enabled_channels:
                    logger.warning(
                        'Skipping patch for %s: Channel %s is not in ACE_ENABLED_CHANNELS. '
                        'Add "%s" to ACE_ENABLED_CHANNELS setting to enable routing.',
                        message_type_path, channel_name, channel_name
                    )
                    continue

                # Dynamically import the message type class
                import importlib
                module = importlib.import_module(module_path)
                message_class = getattr(module, class_name)

                # Save the original __init__
                original_init = message_class.__init__

                # Create a patched __init__ with the channel override
                def make_patched_init(original, channel, msg_type_name):
                    """Factory function to create patched __init__ with correct closure."""

                    def patched_init(self, *args, **kwargs):
                        # Call the original __init__
                        original(self, *args, **kwargs)

                        # Override the channel
                        self.options['override_default_channel'] = channel
                        logger.warning(
                            '%s message created with options: %s (override_default_channel=%s)',
                            msg_type_name, self.options, channel
                        )
                    return patched_init

                # Apply the monkey patch
                message_class.__init__ = make_patched_init(original_init, channel_name, class_name)

                logger.info(
                    'Successfully patched %s to route to %s channel',
                    message_type_path, channel_name
                )
                patched_count += 1

            except (ImportError, AttributeError, ValueError) as e:
                logger.warning(
                    'Could not patch message type %s: %s. '
                    'This message type will use default channel routing.',
                    message_type_path, str(e)
                )

        if patched_count > 0:
            logger.info(
                'Successfully patched %d message type(s) for custom channel routing',
                patched_count
            )
