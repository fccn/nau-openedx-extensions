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

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

try:
    from edx_ace.channel import ChannelType
    from edx_ace.channel.django_email import DjangoEmailChannel
    from edx_ace.errors import FatalChannelDeliveryError
except ImportError:
    # Fallback if edx_ace is not available
    class ChannelType(object):
        """Placeholder ChannelType"""
        EMAIL = 'email'

    class DjangoEmailChannel(object):
        """Placeholder when edx_ace is not available"""

    class FatalChannelDeliveryError(Exception):
        """Placeholder error class"""


logger = logging.getLogger(__name__)


class BulkEmailChannelMixin(object):
    """
    Mixin providing bulk email delivery functionality.

    This mixin can be applied to any ACE channel to enable it to use
    a separate SMTP relay configured specifically for bulk emails.

    The bulk email configuration is completely separate from transactional
    email settings, allowing independent management of infrastructure.
    """

    BULK_EMAIL_HOST_SETTING = 'EMAIL_HOST_FOR_BULK'
    BULK_EMAIL_PORT_SETTING = 'EMAIL_PORT_FOR_BULK'
    BULK_EMAIL_USER_SETTING = 'EMAIL_HOST_USER_FOR_BULK'
    BULK_EMAIL_PASSWORD_SETTING = 'EMAIL_HOST_PASSWORD_FOR_BULK'
    BULK_EMAIL_USE_TLS_SETTING = 'EMAIL_USE_TLS_FOR_BULK'
    BULK_EMAIL_USE_SSL_SETTING = 'EMAIL_USE_SSL_FOR_BULK'
    BULK_EMAIL_TIMEOUT_SETTING = 'EMAIL_TIMEOUT_FOR_BULK'
    BULK_EMAIL_BACKEND_SETTING = 'EMAIL_BACKEND_FOR_BULK'

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
            'Using email backend for bulk: %s',
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

    def _get_bulk_from_address(self, message):
        """
        Get the 'from' address for bulk emails.

        This allows bulk emails to have a different sender address than
        transactional emails if configured.

        Args:
            message: The ACE message object

        Returns:
            str: The email address to use as the sender
        """
        # Check for bulk email specific sender
        bulk_from_address = getattr(settings, 'BULK_EMAIL_FROM_ADDRESS', None)
        if bulk_from_address:
            return bulk_from_address

        # Fall back to standard from address
        return self.get_from_address(message)


class DjangoEmailBulkChannel(BulkEmailChannelMixin, DjangoEmailChannel):
    """
    Custom ACE email channel that uses a separate SMTP relay for bulk emails.

    This channel extends the standard DjangoEmailChannel to support sending emails
    through a different SMTP server configuration (EMAIL_HOST_FOR_BULK and related
    settings) instead of the default EMAIL_HOST.

    Configuration:
        ACE_ENABLED_CHANNELS = [
            'django_email',       # transactional emails
            'django_email_bulk',  # bulk emails (registered via entry point)
        ]

        # Bulk email SMTP relay configuration
        EMAIL_HOST_FOR_BULK = 'bulk-smtp.example.com'
        EMAIL_PORT_FOR_BULK = 587
        EMAIL_HOST_USER_FOR_BULK = 'bulk@example.com'
        EMAIL_HOST_PASSWORD_FOR_BULK = 'password'
        EMAIL_USE_TLS_FOR_BULK = True

        # Optional: different sender for bulk emails
        BULK_EMAIL_FROM_ADDRESS = 'noreply-bulk@example.com'

        # Delivery policies to route bulk emails here
        ACE_DELIVERY_POLICIES = [
            'nau_openedx_extensions.email_channel.delivery_policies.BulkEmailPolicy',
        ]

    The channel is registered via the 'openedx.ace.channel' entry point in setup.py.
    """

    channel_type = ChannelType.EMAIL

    def overrides_delivery_for_message(self, message):
        """
        Indicate that this channel overrides delivery for specific message types.

        This method is used by ACE to determine if this channel should be used
        for delivering a given message based on configured delivery policies.

        This uses the `ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES` setting to check if the
        message type is configured to use this bulk email channel.

        Args:
            message: The ACE message object

        Returns:
            bool: True if this channel overrides delivery for the message
        """
        # This channel is intended for bulk email types only

        # Check if the message type is configured for bulk delivery on ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES setting
        # Get the full message type class path (e.g., 'lms.djangoapps.bulk_email.message_types.BulkEmail')
        message_type = message.__class__.__module__ + '.' + message.__class__.__name__

        # Get the channel overrides configuration
        channel_overrides = getattr(settings, 'ACE_CHANNEL_MESSAGE_TYPE_OVERRIDES', {})

        # Check if this message type is configured to use this channel
        if message_type in channel_overrides:
            configured_channel = channel_overrides[message_type]
            # The channel name for this class is 'django_email_bulk' (registered in setup.py)
            if configured_channel == 'django_email_bulk':
                logger.info(
                    'Message type "%s" is configured for bulk delivery via django_email_bulk channel',
                    message_type
                )
                return True

        logger.debug(
            'Message type "%s" is not configured for bulk delivery (configured for: %s)',
            message_type,
            channel_overrides.get(message_type, 'default')
        )
        return False

    def deliver(self, message, rendered_message):
        """
        Deliver an email message using the bulk SMTP relay.

        This method extends the parent DjangoEmailChannel.deliver() by using
        a custom email connection configured for bulk emails.

        Args:
            message: The ACE message object to deliver
            rendered_message: The rendered message content

        Raises:
            FatalChannelDeliveryError: If SMTP delivery fails
        """
        logger.info(
            'DjangoEmailBulkChannel.deliver() called for recipient: %s',
            message.recipient.email_address if hasattr(message.recipient, 'email_address') else str(message.recipient)
        )

        try:
            # Get the bulk email connection with custom settings
            connection = self._get_bulk_connection()
            logger.info('Bulk email connection created successfully')

            subject = self.get_subject(rendered_message)
            from_address = self._get_bulk_from_address(message)
            reply_to = message.options.get('reply_to', None)

            logger.info(
                'Email details - Subject: %s, From: %s, To: %s',
                subject, from_address, message.recipient.email_address
            )

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

        except Exception as e:  # pylint: disable=broad-except
            logger.exception('Error delivering bulk email message: %s', e)
            raise FatalChannelDeliveryError(
                'An error occurred while delivering bulk email: {}'.format(str(e))
            ) from e
