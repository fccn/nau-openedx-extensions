# -*- coding: utf-8 -*-
"""
Settings for the email_channel module.

This module provides configuration for custom ACE email channels
that support different SMTP relays for bulk email delivery.
"""
from __future__ import absolute_import, unicode_literals


def plugin_settings(settings):
    """
    Configure email channel settings when app is used as a plugin to edx-platform.

    These settings allow configuration of a separate SMTP relay for bulk email delivery,
    independent of the transactional email system.

    Args:
        settings: Django settings object

    Note:
        This function intentionally does NOT set default values for EMAIL_*_FOR_BULK
        settings. The defaults are handled at runtime in django_email_bulk.py to ensure
        EMAIL_HOST and other standard Django email settings are already loaded.

        Only the EMAIL_BACKEND_FOR_BULK has a default set here based on DEBUG mode
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
