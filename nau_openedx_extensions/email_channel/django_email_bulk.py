# -*- coding: utf-8 -*-
"""
Custom ACE email channel using a separate SMTP relay for bulk emails.

This module provides a custom implementation of the edX ACE DjangoEmailChannel
that allows sending emails through a different SMTP server than the default
transactional email system.

This is particularly useful for organizations using separate email infrastructure
for marketing/bulk emails (e.g., Portuguese public contracting requirements).
"""
from __future__ import absolute_import, unicode_literals

import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

try:
    from edx_ace.channel.django_email import DjangoEmailChannel
    from edx_ace.errors import FatalChannelDeliveryError
except ImportError:
    # Fallback if edx_ace is not available
    DjangoEmailChannel = object
    FatalChannelDeliveryError = Exception

logger = logging.getLogger(__name__)


class DjangoEmailBulkChannel(DjangoEmailChannel):
    """
    Custom ACE email channel that uses a separate SMTP relay for bulk emails.

    This channel extends the standard DjangoEmailChannel to support sending emails
    through a different SMTP server configuration (EMAIL_HOST_FOR_BULK and related
    settings) instead of the default EMAIL_HOST.

    Configuration:
        - EMAIL_HOST_FOR_BULK: SMTP host for bulk emails (defaults to EMAIL_HOST)
        - EMAIL_PORT_FOR_BULK: SMTP port for bulk emails (defaults to EMAIL_PORT)
        - EMAIL_HOST_USER_FOR_BULK: Username for bulk email SMTP (defaults to EMAIL_HOST_USER)
        - EMAIL_HOST_PASSWORD_FOR_BULK: Password for bulk email SMTP (defaults to EMAIL_HOST_PASSWORD)
        - EMAIL_USE_TLS_FOR_BULK: Use TLS for bulk emails (defaults to EMAIL_USE_TLS)
        - EMAIL_USE_SSL_FOR_BULK: Use SSL for bulk emails (defaults to EMAIL_USE_SSL)
        - EMAIL_TIMEOUT_FOR_BULK: Connection timeout in seconds (defaults to EMAIL_TIMEOUT or 10)

    Usage:
        1. Install the package to register the entry point:
           pip install -e .

        2. Configure in Django settings:
           ACE_ENABLED_CHANNELS = [
               'django_email_bulk',  # Entry point name from setup.py
           ]

        3. Configure bulk email settings:
           EMAIL_HOST_FOR_BULK = 'bulk-smtp.example.com'
           EMAIL_PORT_FOR_BULK = 587
           EMAIL_HOST_USER_FOR_BULK = 'bulk@example.com'
           EMAIL_HOST_PASSWORD_FOR_BULK = 'password'
           EMAIL_USE_TLS_FOR_BULK = True

    Note: The channel is registered via the 'openedx.ace.channel' entry point
          in setup.py, not by module path.
    """

    def deliver(self, message, rendered_message):
        """
        Deliver an email message using the bulk SMTP relay.

        This method is based on the parent DjangoEmailChannel.deliver() but passes
        a custom email connection configured for bulk emails instead of the default
        transactional email configuration.

        Args:
            message: The ACE message object to deliver
            rendered_message: The rendered message content

        Raises:
            FatalChannelDeliveryError: If SMTP delivery fails
        """
        try:
            # Get the bulk email connection with custom settings
            connection = self._get_bulk_connection()

            subject = self.get_subject(rendered_message)
            from_address = self.get_from_address(message)
            reply_to = message.options.get('reply_to', None)

            rendered_template = self.make_simple_html_template(
                rendered_message.head_html,
                rendered_message.body_html
            )

            # Pass the custom connection to EmailMultiAlternatives
            mail = EmailMultiAlternatives(
                subject=subject,
                body=rendered_message.body,
                from_email=from_address,
                to=[message.recipient.email_address],
                reply_to=reply_to,
                headers=getattr(message, 'headers', None),
                connection=connection,
            )

            mail.attach_alternative(rendered_template, 'text/html')
            mail.send()

            logger.info(
                'Successfully delivered bulk email to user %s via channel %s',
                message.recipient.username
                if hasattr(message.recipient, 'username')
                else str(message.recipient),
                self.channel_type,
            )

        except SMTPException as e:
            logger.exception(e)
            raise FatalChannelDeliveryError(
                'An SMTP error occurred (and logged) from Django send_email()'
            ) from e

    @staticmethod
    def _get_bulk_connection():
        """
        Create and return a Django email connection using bulk email settings.

        This method constructs a connection using EMAIL_HOST_FOR_BULK and related
        settings, falling back to the standard EMAIL_HOST settings if bulk-specific
        settings are not configured.

        Returns:
            A Django email backend connection instance

        Raises:
            Exception: If the connection fails to be created
        """
        # Get bulk email settings, falling back to standard settings
        email_host = getattr(
            settings,
            'EMAIL_HOST_FOR_BULK',
            getattr(settings, 'EMAIL_HOST', 'localhost')
        )
        email_port = getattr(
            settings,
            'EMAIL_PORT_FOR_BULK',
            getattr(settings, 'EMAIL_PORT', 25)
        )
        email_host_user = getattr(
            settings,
            'EMAIL_HOST_USER_FOR_BULK',
            getattr(settings, 'EMAIL_HOST_USER', '')
        )
        email_host_password = getattr(
            settings,
            'EMAIL_HOST_PASSWORD_FOR_BULK',
            getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        )
        email_use_tls = getattr(
            settings,
            'EMAIL_USE_TLS_FOR_BULK',
            getattr(settings, 'EMAIL_USE_TLS', True)
        )
        email_use_ssl = getattr(
            settings,
            'EMAIL_USE_SSL_FOR_BULK',
            getattr(settings, 'EMAIL_USE_SSL', False)
        )
        email_timeout = getattr(
            settings,
            'EMAIL_TIMEOUT_FOR_BULK',
            getattr(settings, 'EMAIL_TIMEOUT', 10)
        )

        logger.info(
            'Creating bulk email connection: host=%s, port=%s, use_tls=%s, use_ssl=%s, timeout=%s',
            email_host,
            email_port,
            email_use_tls,
            email_use_ssl,
            email_timeout
        )

        # Get the email backend to use (defaults to SMTP)
        email_backend = getattr(
            settings,
            'EMAIL_BACKEND_FOR_BULK',
            'django.core.mail.backends.smtp.EmailBackend'
        )

        logger.info(
            'Using email backend: %s',
            email_backend
        )

        try:
            connection = get_connection(
                backend=email_backend,
                host=email_host,
                port=email_port,
                username=email_host_user,
                password=email_host_password,
                use_tls=email_use_tls,
                use_ssl=email_use_ssl,
                timeout=email_timeout,
                fail_silently=False,
            )
            return connection
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                'Failed to create bulk email connection: %s',
                str(e)
            )
            raise
