# -*- coding: utf-8 -*-
"""
Settings for the email_channel module.

This module provides configuration for custom ACE email channels
that support different SMTP relays for bulk email delivery.

Features:
    - Separate SMTP relay for bulk emails
    - ACE Delivery Policy for message-based routing
    - Automatic bulk email detection and routing
"""
from __future__ import absolute_import, unicode_literals


def plugin_settings(settings):
    """
    Configure email channel settings when app is used as a plugin to edx-platform.

    These settings allow configuration of a separate SMTP relay for bulk email delivery,
    independent of the transactional email system.

    Args:
        settings: Django settings object

    Configuration Options:
        EMAIL_BACKEND_FOR_BULK:
            Email backend for bulk emails. Defaults to console backend for DEBUG=True,
            SMTP backend for production.

        EMAIL_HOST_FOR_BULK, EMAIL_PORT_FOR_BULK, etc.:
            Connection settings for bulk email SMTP relay. Defaults to standard
            EMAIL_HOST, EMAIL_PORT, etc. if not explicitly configured.

        ACE_ENABLED_CHANNELS:
            List of enabled ACE channels. Must include both 'django_email' and
            'django_email_bulk' (registered via entry point in setup.py).

        ACE_CHANNEL_DEFAULT_EMAIL:
            Default channel for emails. Usually 'django_email'.

    Note:
        - Intentionally does NOT set default values for EMAIL_*_FOR_BULK settings;
          defaults are handled at runtime to ensure standard EMAIL_* settings are loaded first.
        - The EMAIL_BACKEND_FOR_BULK has a default set here based on DEBUG mode
          to provide a good development experience out of the box.
    """

    # Email backend for bulk emails
    # For development (DEBUG=True), defaults to console backend to avoid SMTP connection issues
    # For production (DEBUG=False), defaults to SMTP backend
    # Can be explicitly overridden in environment configuration
    if not hasattr(settings, 'EMAIL_BACKEND_FOR_BULK'):
        if getattr(settings, 'DEBUG', False):
            # Development: print emails to console/logs
            settings.EMAIL_BACKEND_FOR_BULK = 'django.core.mail.backends.console.EmailBackend'
        else:
            # Production: use SMTP backend
            settings.EMAIL_BACKEND_FOR_BULK = 'django.core.mail.backends.smtp.EmailBackend'

    # Ensure both standard and bulk email channels are enabled
    if not hasattr(settings, 'ACE_ENABLED_CHANNELS'):
        settings.ACE_ENABLED_CHANNELS = [
            'django_email',       # transactional emails
            'django_email_bulk',  # bulk emails (registered via entry point)
        ]
    else:
        # Ensure bulk channel is in the list if not already present
        if 'django_email_bulk' not in settings.ACE_ENABLED_CHANNELS:
            settings.ACE_ENABLED_CHANNELS = list(settings.ACE_ENABLED_CHANNELS) + ['django_email_bulk']

    # Default email channel (for standard transactional emails)
    if not hasattr(settings, 'ACE_CHANNEL_DEFAULT_EMAIL'):
        settings.ACE_CHANNEL_DEFAULT_EMAIL = 'django_email'

    # Message type to channel routing configuration
    # ================================================
    # This maps edx-platform message types to specific ACE channels via monkey patching.
    # The app automatically patches each message type's __init__ to set override_default_channel.
    #
    # Format: {'full.module.path.MessageClassName': 'channel_name'}
    #
    # To add a new message type:
    #   1. Find the message type class path (e.g., grep for "class.*Message" in edx-platform)
    #   2. Add entry here mapping to your target channel
    #   3. Ensure channel exists and is registered in setup.py
    #   4. Add channel to ACE_ENABLED_CHANNELS below
    #   5. Configure EMAIL_*_FOR_<CHANNEL> settings if using custom SMTP
    #   6. Restart services
    #
    # Common message types you might want to route:
    #   - lms.djangoapps.bulk_email.message_types.BulkEmail - Course announcements/emails
    #   - lms.djangoapps.verify_student.messages.* - ID verification emails
    #   - lms.djangoapps.grades.messages.* - Grade-related emails
    #   - openedx.core.djangoapps.user_authn.views.password_reset.PasswordReset - Password resets
    #
    # Example configuration for multiple channels:
    #   ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES = {
    #       'lms.djangoapps.bulk_email.message_types.BulkEmail': 'django_email_bulk',
    #       'lms.djangoapps.verify_student.messages.VerificationReminder': 'django_email_transactional',
    #       'custom.app.message_types.MarketingEmail': 'django_email_marketing',
    #   }
    #
    # Then configure each channel's SMTP settings:
    #   EMAIL_HOST_FOR_BULK = 'bulk-smtp.example.com'
    #   EMAIL_HOST_FOR_TRANSACTIONAL = 'transactional-smtp.example.com'
    #   EMAIL_HOST_FOR_MARKETING = 'marketing-smtp.example.com'
    #
    if not hasattr(settings, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES'):
        settings.ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES = {
            # BulkEmail messages from lms.djangoapps.bulk_email go to bulk channel
            'lms.djangoapps.bulk_email.message_types.BulkEmail': 'django_email_bulk',
            # All schedule module message types go to bulk channel
            'openedx.core.djangoapps.schedules.message_types.RecurringNudge': 'django_email_bulk',
            'openedx.core.djangoapps.schedules.message_types.UpgradeReminder': 'django_email_bulk',
            'openedx.core.djangoapps.schedules.message_types.CourseUpdate': 'django_email_bulk',
            'openedx.core.djangoapps.schedules.message_types.InstructorLedCourseUpdate': 'django_email_bulk',
        }
