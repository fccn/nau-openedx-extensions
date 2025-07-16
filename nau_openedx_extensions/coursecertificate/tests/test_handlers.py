"""
Unit tests for coursecertificate handlers.
"""

from unittest.mock import Mock, patch

from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from openedx_events.data import EventsMetadata
from openedx_events.learning.data import CertificateData, CourseData, UserData, UserPersonalData
from openedx_events.learning.signals import CERTIFICATE_CREATED

from nau_openedx_extensions.coursecertificate.handlers import certificate_created_send_to_external_services_handler
from nau_openedx_extensions.coursecertificate.tests.fixtures import Certificate, User


class TestCertificateCreatedHandler(TestCase):
    """
    Tests for the certificate_created_send_to_external_services_handler.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User()
        self.certificate = Certificate(self.user)

        self.user_data = UserData(
            pii=UserPersonalData(
                username=self.user.username,
                email=self.user.email,
                name=self.user.profile.name,
            ),
            id=self.user.id,
            is_active=True,
        )

        self.course_data = CourseData(
            course_key=self.certificate.course_id,
            display_name=self.certificate.course_id.course,
            start=None,
            end=None,
        )

        self.certificate_data = CertificateData(
            user=self.user_data,
            course=self.course_data,
            mode=self.certificate.mode,
            grade=self.certificate.grade,
            download_url=f"https://lms.example.com/certificates/{self.certificate.verify_uuid}",
            name=self.certificate.name,
            current_status=self.certificate.status,
            previous_status=None,
        )

        self.metadata = EventsMetadata(
            event_type="org.openedx.learning.certificate.created.v1",
            minorversion=0,
        )

    @patch("nau_openedx_extensions.coursecertificate.handlers.log")
    @patch("nau_openedx_extensions.coursecertificate.handlers.call_command")
    @patch("nau_openedx_extensions.coursecertificate.handlers.GeneratedCertificate")
    def test_certificate_created_handler_success(
        self, mock_certificate_model: Mock, mock_call_command: Mock, mock_log: Mock
    ):
        """
        Test successful execution of certificate created handler.

        Expected behavior:
        - Handler retrieves the GeneratedCertificate from database using user_id and course_id
        - Handler logs info message about sending certificate to external services
        - Handler calls the send_certificates_by_web_service command with certificate_id
        """
        mock_certificate_model.objects.get.return_value = self.certificate

        CERTIFICATE_CREATED.connect(certificate_created_send_to_external_services_handler)
        CERTIFICATE_CREATED.send_event(certificate=self.certificate_data)

        mock_certificate_model.objects.get.assert_called_once_with(
            user_id=self.user.id, course_id=self.certificate.course_id
        )
        mock_call_command.assert_called_once_with(
            "send_certificates_by_web_service", certificate_id=self.certificate.id, async_mode=True
        )
        mock_log.info.assert_called_once_with(f"Sending certificate {self.certificate.id} to external services")

    @patch("nau_openedx_extensions.coursecertificate.handlers.log")
    @patch("nau_openedx_extensions.coursecertificate.handlers.call_command")
    @patch("nau_openedx_extensions.coursecertificate.handlers.GeneratedCertificate")
    def test_certificate_created_handler_certificate_not_found(
        self, mock_certificate_model: Mock, mock_call_command: Mock, mock_log: Mock
    ):
        """
        Test handler behavior when certificate is not found in database.

        Expected behavior:
        - Handler logs an error when certificate doesn't exist
        - Handler returns early without calling the command
        - Command should not be called
        """
        mock_certificate_model.DoesNotExist = ObjectDoesNotExist
        mock_certificate_model.objects.get.side_effect = mock_certificate_model.DoesNotExist("Certificate not found")

        CERTIFICATE_CREATED.connect(certificate_created_send_to_external_services_handler)
        CERTIFICATE_CREATED.send_event(certificate=self.certificate_data)

        mock_call_command.assert_not_called()
        mock_log.error.assert_called_once_with(
            f"No GeneratedCertificate found for user_id={self.user.id} and course_id={self.certificate.course_id}"
        )

    @patch("nau_openedx_extensions.coursecertificate.handlers.log")
    @patch("nau_openedx_extensions.coursecertificate.handlers.call_command")
    @patch("nau_openedx_extensions.coursecertificate.handlers.GeneratedCertificate")
    def test_certificate_created_handler_command_failure(
        self, mock_certificate_model: Mock, mock_call_command: Mock, mock_log: Mock
    ):
        """
        Test handler behavior when the management command fails.

        Expected behavior:
        - Handler catches command exceptions and logs them
        - Handler logs error with exception details
        - Handler does not re-raise the exception
        """
        mock_certificate_model.objects.get.return_value = self.certificate
        mock_call_command.side_effect = Exception("Command failed")

        CERTIFICATE_CREATED.connect(certificate_created_send_to_external_services_handler)
        CERTIFICATE_CREATED.send_event(certificate=self.certificate_data)

        mock_call_command.assert_called_once_with(
            "send_certificates_by_web_service", certificate_id=self.certificate.id, async_mode=True
        )
        mock_log.error.assert_called_once_with(
            f"Failed to send certificate {self.certificate.id} to external services: Command failed", exc_info=True
        )
