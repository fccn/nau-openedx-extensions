"""
Tests for async mode and Celery tasks.
"""
from unittest.mock import Mock, patch

from django.test import TestCase

from nau_openedx_extensions.coursecertificate.tasks import process_service_certificates

TASK_MODULE_PATH = "nau_openedx_extensions.coursecertificate.tasks"


class TestCeleryTaskEdgeCases(TestCase):
    """
    Test edge cases for Celery task.
    """

    @patch(f"{TASK_MODULE_PATH}.CertificateEngine")
    def test_task_with_empty_service_config(self, mock_engine_class):
        """Test task with empty service configuration."""

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        result = process_service_certificates({}, {"dry_run": False})  # pylint: disable=no-value-for-parameter

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["service_name"], "unknown")

    @patch(f"{TASK_MODULE_PATH}.CertificateEngine")
    def test_task_with_none_service_config(self, mock_engine_class):
        """Test task with None service configuration."""

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        with self.assertRaises(AttributeError) as context:
            process_service_certificates(None, {"dry_run": False})  # pylint: disable=no-value-for-parameter

        self.assertIn("'NoneType' object has no attribute 'get'", str(context.exception))

    @patch(f"{TASK_MODULE_PATH}.CertificateEngine")
    def test_task_with_none_options(self, mock_engine_class):
        """Test task with None options."""

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine
        service_config = {"service_name": "test"}

        result = process_service_certificates(service_config, None)  # pylint: disable=no-value-for-parameter

        self.assertEqual(result["status"], "success")
        mock_engine.process_service.assert_called_once_with(service_config, None)

    @patch(f"{TASK_MODULE_PATH}.CertificateEngine")
    def test_task_logger_functionality(self, mock_engine_class):
        """Test that task logger works correctly."""

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        result = process_service_certificates(  # pylint: disable=no-value-for-parameter
            {"service_name": "logger_test"},
            {"dry_run": False}
        )

        self.assertEqual(result["status"], "success")
        mock_engine.process_service.assert_called_once_with(
            {"service_name": "logger_test"},
            {"dry_run": False}
        )
