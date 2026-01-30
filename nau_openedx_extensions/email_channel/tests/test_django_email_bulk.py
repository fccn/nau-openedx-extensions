# -*- coding: utf-8 -*-
"""
Tests for the DjangoEmailBulkChannel
"""
from __future__ import absolute_import, unicode_literals

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

try:
    from edx_ace.message import Message
    from edx_ace.recipient import Recipient
    ACE_AVAILABLE = True
except ImportError:
    ACE_AVAILABLE = False

from nau_openedx_extensions.email_channel.django_email_bulk import DjangoEmailBulkChannel


class DjangoEmailBulkChannelTestCase(TestCase):
    """
    Test cases for DjangoEmailBulkChannel
    """

    def setUp(self):
        """Set up test fixtures"""
        self.channel = DjangoEmailBulkChannel()
        User = get_user_model()
        self.user = User(
            username='testuser',
            email='testuser@example.com',
            first_name='Test',
            last_name='User'
        )

    @override_settings(
        EMAIL_HOST_FOR_BULK='bulk-smtp.example.com',
        EMAIL_PORT_FOR_BULK=587,
        EMAIL_HOST_USER_FOR_BULK='bulk@example.com',
        EMAIL_HOST_PASSWORD_FOR_BULK='password123',
        EMAIL_USE_TLS_FOR_BULK=True,
        EMAIL_USE_SSL_FOR_BULK=False,
        EMAIL_TIMEOUT_FOR_BULK=10,
    )
    def test_get_bulk_connection_with_custom_settings(self):
        """Test _get_bulk_connection with custom bulk settings"""
        connection = self.channel._get_bulk_connection()  # pylint: disable=protected-access

        self.assertIsNotNone(connection)
        self.assertEqual(connection.host, 'bulk-smtp.example.com')
        self.assertEqual(connection.port, 587)
        self.assertEqual(connection.username, 'bulk@example.com')
        self.assertEqual(connection.password, 'password123')
        self.assertTrue(connection.use_tls)
        self.assertFalse(connection.use_ssl)
        self.assertEqual(connection.timeout, 10)

    @override_settings(
        EMAIL_HOST='default-smtp.example.com',
        EMAIL_PORT=25,
        EMAIL_HOST_USER='default@example.com',
        EMAIL_HOST_PASSWORD='default_password',
        EMAIL_USE_TLS=False,
        EMAIL_USE_SSL=False,
    )
    def test_get_bulk_connection_fallback_to_default(self):
        """Test _get_bulk_connection falls back to default EMAIL settings"""
        connection = self.channel._get_bulk_connection()  # pylint: disable=protected-access

        self.assertIsNotNone(connection)
        self.assertEqual(connection.host, 'default-smtp.example.com')
        self.assertEqual(connection.port, 25)
        self.assertEqual(connection.username, 'default@example.com')
        self.assertEqual(connection.password, 'default_password')

    @override_settings(
        EMAIL_HOST_FOR_BULK='bulk-smtp.example.com',
        EMAIL_PORT_FOR_BULK=587,
        EMAIL_HOST_USER_FOR_BULK='bulk@example.com',
        EMAIL_HOST_PASSWORD_FOR_BULK='password123',
        EMAIL_USE_TLS_FOR_BULK=True,
    )
    @mock.patch('nau_openedx_extensions.email_channel.django_email_bulk.get_connection')
    def test_deliver_calls_parent_with_connection(self, mock_get_connection):
        """Test deliver method passes custom connection to EmailMultiAlternatives"""
        if not ACE_AVAILABLE:
            self.skipTest('edx_ace not available')

        # Mock the connection
        mock_connection = mock.MagicMock()
        mock_get_connection.return_value = mock_connection

        # Create a Recipient object from the user
        recipient = Recipient(self.user.username, self.user.email)
        message = Message(
            app_label='test_app',
            name='test_message',
            recipient=recipient,
        )

        # Create a mock rendered message with required attributes
        rendered_message = mock.MagicMock()
        rendered_message.subject = 'Test Subject'
        rendered_message.body = 'Test body'
        rendered_message.head_html = '<h1>Test</h1>'
        rendered_message.body_html = '<p>Test body</p>'

        # Mock EmailMultiAlternatives to avoid actual SMTP calls
        with mock.patch(
            'nau_openedx_extensions.email_channel.django_email_bulk.EmailMultiAlternatives'
        ) as mock_email:
            mock_mail_instance = mock.MagicMock()
            mock_email.return_value = mock_mail_instance

            self.channel.deliver(message, rendered_message)

            # Verify EmailMultiAlternatives was called with the custom connection
            mock_email.assert_called_once()
            call_kwargs = mock_email.call_args[1]
            self.assertEqual(call_kwargs['connection'], mock_connection)

    @override_settings(
        EMAIL_HOST_FOR_BULK='bulk-smtp.example.com',
        EMAIL_PORT_FOR_BULK=587,
    )
    @mock.patch('nau_openedx_extensions.email_channel.django_email_bulk.get_connection')
    def test_get_bulk_connection_called_with_correct_params(self, mock_get_connection):
        """Test _get_bulk_connection passes correct parameters to get_connection"""
        mock_connection = mock.MagicMock()
        mock_get_connection.return_value = mock_connection

        self.channel._get_bulk_connection()  # pylint: disable=protected-access

        mock_get_connection.assert_called_once()
        call_kwargs = mock_get_connection.call_args[1]

        self.assertEqual(call_kwargs['host'], 'bulk-smtp.example.com')
        self.assertEqual(call_kwargs['port'], 587)
        self.assertEqual(call_kwargs['backend'], 'django.core.mail.backends.smtp.EmailBackend')

    @override_settings(
        EMAIL_HOST_FOR_BULK='invalid-host',
        EMAIL_PORT_FOR_BULK=999999,
    )
    @mock.patch('nau_openedx_extensions.email_channel.django_email_bulk.get_connection')
    def test_get_bulk_connection_handles_error(self, mock_get_connection):
        """Test _get_bulk_connection handles connection errors gracefully"""
        mock_get_connection.side_effect = Exception('Connection failed')

        with self.assertRaises(Exception):
            self.channel._get_bulk_connection()  # pylint: disable=protected-access
