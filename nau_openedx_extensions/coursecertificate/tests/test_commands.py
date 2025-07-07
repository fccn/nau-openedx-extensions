"""
Tests for the send_certificates_by_web_service management command.
"""

import base64
import hashlib
import json
import os
import tempfile
from io import StringIO
from unittest.mock import Mock, mock_open, patch

import yaml
from django.core.management.base import CommandError, OutputWrapper
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.coursecertificate.management.commands.send_certificates_by_web_service import Command
from nau_openedx_extensions.coursecertificate.tests.fixtures import Certificate, User

COMMAND_MODULE_PATH = "nau_openedx_extensions.coursecertificate.management.commands.send_certificates_by_web_service"


class TestSendCertificatesByWebServiceCommand(TestCase):
    """
    Test the send_certificates_by_web_service management command.
    """

    def setUp(self):
        """Set up test data and configuration."""
        self.command = Command()
        self.command.stdout = OutputWrapper(StringIO())
        self.command.stderr = OutputWrapper(StringIO())

        # Sample configuration
        self.sample_config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "test_service",
                    "endpoint_url": "https://api.test.com/certificates",
                    "auth_token": "test_token",
                    "auth_type": "bearer",
                    "auth_header": "Authorization",
                    "days": 7,
                    "page_size": 100,
                    "fields": [
                        {
                            "name": "certificate_id",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.certificate.key",
                        },
                        {
                            "name": "student_email",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
                        },
                        {
                            "name": "course_id",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.course.id",
                        },
                        {
                            "name": "hashed_email",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
                            "trans": "md5",
                        },
                        {
                            "name": "encoded_course",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.course.code",
                            "trans": "base64",
                        },
                    ],
                    "filters": [
                        {
                            "func": "nau_openedx_extensions.coursecertificate.filters.pipeline.filter_by_status",
                            "args": ["downloadable"],
                        },
                    ],
                }
            ]
        }

        # Create test certificates
        self.user1 = User()
        self.user2 = User()
        self.users = [self.user1, self.user2]
        self.certificate1 = Certificate(self.user1)
        self.certificate2 = Certificate(self.user2)
        self.certificates = [self.certificate1, self.certificate2]

    def test_get_default_config_path(self):
        """Test getting the default configuration file path."""
        config_path = self.command.get_default_config_path()

        self.assertIsInstance(config_path, str)
        self.assertTrue(config_path.endswith("config.yml"))
        self.assertTrue(os.path.isabs(config_path))

    def test_load_config_success(self):
        """Test loading configuration from a valid YAML file."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_service")
        self.assertEqual(config[0]["endpoint_url"], "https://api.test.com/certificates")

    def test_load_config_file_not_found(self):
        """Test loading configuration when file doesn't exist."""
        with self.assertRaises(CommandError) as context:
            self.command.load_config("/nonexistent/path/config.yml")

        self.assertIn("Configuration file not found", str(context.exception))

    def test_load_config_invalid_yaml(self):
        """Test loading configuration with invalid YAML."""
        invalid_yaml = "invalid: yaml: content: ["

        with patch("builtins.open", mock_open(read_data=invalid_yaml)):
            with self.assertRaises(CommandError) as context:
                self.command.load_config("/fake/path/config.yml")

        self.assertIn("Error parsing YAML configuration", str(context.exception))

    def test_apply_transformations_md5(self):
        """Test MD5 transformation."""
        test_value = "test@example.com"
        result = self.command.apply_transformations(test_value, "md5")

        expected = hashlib.md5(test_value.encode()).hexdigest()
        self.assertEqual(result, expected)

    def test_apply_transformations_base64(self):
        """Test base64 transformation."""
        test_value = "test-course"
        result = self.command.apply_transformations(test_value, "base64")

        expected = base64.b64encode(test_value.encode()).decode()
        self.assertEqual(result, expected)

    def test_apply_transformations_unknown(self):
        """Test unknown transformation returns original value."""
        test_value = "test_value"
        result = self.command.apply_transformations(test_value, "unknown_trans")

        self.assertEqual(result, test_value)

    def test_extract_field_value_success(self):
        """Test successful field value extraction."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
        }
        certificate = Mock()
        certificate.user.email = "test@example.com"
        result = self.command.extract_field_value(certificate, field_config)

        self.assertEqual(result, "test@example.com")

    def test_extract_field_value_with_args(self):
        """Test field value extraction with arguments."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student.nau_user_extended_model_field",
            "args": ["nif"],
        }

        certificate = Mock()
        certificate.user.nauuserextendedmodel.nif = "123456789"
        result = self.command.extract_field_value(certificate, field_config)

        self.assertEqual(result, "123456789")

    def test_extract_field_value_with_transformation_md5(self):
        """Test field value extraction with transformation."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
            "trans": "md5",
        }
        certificate = Mock()
        certificate.user.email = "test@example.com"
        result = self.command.extract_field_value(certificate, field_config)
        expected = hashlib.md5("test@example.com".encode()).hexdigest()
        self.assertEqual(result, expected)

    def test_extract_field_value_with_transformation_base64(self):
        """Test field value extraction with transformation."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
            "trans": "base64",
        }
        certificate = Mock()
        certificate.user.email = "test@example.com"
        result = self.command.extract_field_value(certificate, field_config)
        expected = base64.b64encode("test@example.com".encode()).decode()
        self.assertEqual(result, expected)

    def test_extract_field_value_import_error(self):
        """Test field value extraction with import error."""
        field_config = {
            "name": "test_field",
            "func": "nonexistent.module.function",
        }
        certificate = Mock()
        result = self.command.extract_field_value(certificate, field_config)

        self.assertIsNone(result)

    def test_extract_field_value_attribute_error(self):
        """Test field value extraction with attribute error."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student.nonexistent_function",
        }
        certificate = Mock()
        result = self.command.extract_field_value(certificate, field_config)

        self.assertIsNone(result)

    def test_apply_filters_success(self):
        """Test applying filters successfully."""
        self.certificates[0].course_id = CourseKey.from_string("course-v1:NAU+Demo1+Course")
        self.certificates[1].course_id = CourseKey.from_string("course-v1:OpenedX+Demo2+Course")
        certificate_3 = Certificate(User())
        certificate_3.course_id = CourseKey.from_string("course-v1:edunext+Demo3+Course")
        self.certificates.append(certificate_3)

        service_config = {
            "filters": [
                {
                    "func": "nau_openedx_extensions.coursecertificate.filters.certificate_by_org",
                    "args": "NAU",
                }
            ]
        }

        result = self.command.apply_filters(self.certificates, service_config)

        self.assertEqual(len(result), 1)
        certificate = result[0]
        self.assertEqual(certificate.course_id, CourseKey.from_string("course-v1:NAU+Demo1+Course"))
        self.assertEqual(certificate.user.email, self.user1.email)
        self.assertEqual(certificate.grade, self.certificate1.grade)
        self.assertEqual(certificate.created_date, self.certificate1.created_date)
        self.assertEqual(certificate.modified_date, self.certificate1.modified_date)
        self.assertEqual(certificate.status, self.certificate1.status)
        self.assertEqual(certificate.mode, self.certificate1.mode)
        self.assertEqual(certificate.name, self.certificate1.name)

    def test_apply_filters_import_error(self):
        """Test applying filters with import error."""
        service_config = {
            "filters": [
                {
                    "func": "nonexistent.module.function",
                }
            ]
        }

        result = self.command.apply_filters(self.certificates, service_config)

        # Should return original queryset when filter fails
        self.assertEqual(result, self.certificates)

    def test_convert_certificates_to_service_format(self):
        """Test converting certificates to service format."""
        service_config = {
            "fields": [
                {
                    "name": "certificate_date",
                    "func": "nau_openedx_extensions.coursecertificate.extractors.certificate.date",
                },
                {
                    "name": "student_email",
                    "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
                },
            ]
        }
        result = self.command.convert_certificates_to_service_format(self.certificates, service_config)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["student_email"], self.user1.email)
        self.assertEqual(result[0]["certificate_date"], self.certificate1.created_date.isoformat())
        self.assertEqual(result[1]["student_email"], self.user2.email)
        self.assertEqual(result[1]["certificate_date"], self.certificate2.created_date.isoformat())

    def test_convert_certificates_with_failed_extraction(self):
        """Test converting certificates when a field extraction fails."""
        service_config = {
            "fields": [
                {
                    "name": "valid_field",
                    "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
                },
                {
                    "name": "invalid_field",
                    "func": "nonexistent.module.function",  # This will fail
                },
            ]
        }

        result = self.command.convert_certificates_to_service_format(self.certificates, service_config)

        self.assertEqual(len(result), 2)
        self.assertIn("valid_field", result[0])
        self.assertNotIn("invalid_field", result[0])
        self.assertIn("valid_field", result[1])
        self.assertNotIn("invalid_field", result[1])

    @patch("requests.post")
    def test_send_certificates_to_service_success(self, mock_post: Mock):
        """Test successful sending of certificates to service."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.text = "Success"
        mock_post.return_value = mock_response

        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "bearer",
        }

        certificates_data = [{"certificate_id": "123", "email": "test@example.com"}]

        result = self.command.send_certificates_to_service(service_config, certificates_data)

        self.assertTrue(result)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://api.test.com/certificates")
        self.assertEqual(call_args[1]["json"], certificates_data)
        self.assertIn("Authorization", call_args[1]["headers"])

    @patch("requests.post")
    def test_send_certificates_to_service_failure(self, mock_post: Mock):
        """Test failed sending of certificates to service."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.text = "Error"
        mock_post.return_value = mock_response

        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
        }

        certificates_data = [{"certificate_id": "123"}]

        result = self.command.send_certificates_to_service(service_config, certificates_data)

        self.assertFalse(result)

    @patch("requests.post")
    def test_send_certificates_to_service_request_exception(self, mock_post: Mock):
        """Test sending certificates with request exception."""
        mock_post.side_effect = Exception("Connection error")

        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
        }

        certificates_data = [{"certificate_id": "123"}]

        with self.assertRaises(Exception):
            result = self.command.send_certificates_to_service(service_config, certificates_data)
            self.assertFalse(result)

    @patch("requests.post")
    def test_send_certificates_to_service_dry_run(self, mock_post: Mock):
        """Test sending certificates in dry run mode."""
        self.command.dry_run = True

        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "bearer",
        }

        certificates_data = [{"certificate_id": "123", "email": "test@example.com"}]

        result = self.command.send_certificates_to_service(service_config, certificates_data)

        self.assertTrue(result)
        mock_post.assert_not_called()
        output = self.command.stdout.getvalue()
        self.assertIn(f"[DRY RUN] Would send to {service_config['endpoint_url']}", output)
        self.assertIn(f"[DRY RUN] Headers would include: {service_config['auth_type']} authentication", output)
        self.assertIn("[DRY RUN] Auth header: Authorization", output)
        self.assertIn("[DRY RUN] Payload:", output)
        self.assertIn(json.dumps(certificates_data, indent=2, ensure_ascii=False), output)

    def test_send_certificates_to_service_basic_auth(self):
        """Test sending certificates with basic authentication."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "user:pass",
            "auth_type": "basic",
        }

        certificates_data = [{"certificate_id": "123"}]

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.ok = True
            mock_post.return_value = mock_response

            self.command.send_certificates_to_service(service_config, certificates_data)

            call_args = mock_post.call_args
            headers = call_args[1]["headers"]
            self.assertIn("Authorization", headers)
            self.assertTrue(headers["Authorization"].startswith("Basic "))

    def test_send_certificates_to_service_api_key_auth(self):
        """Test sending certificates with API key authentication."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "api_key_123",
            "auth_type": "api_key",
            "auth_header": "X-API-Key",
        }

        certificates_data = [{"certificate_id": "123"}]

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.ok = True
            mock_post.return_value = mock_response

            self.command.send_certificates_to_service(service_config, certificates_data)

            call_args = mock_post.call_args
            headers = call_args[1]["headers"]
            self.assertIn("X-API-Key", headers)
            self.assertEqual(headers["X-API-Key"], "api_key_123")

    @patch(f"{COMMAND_MODULE_PATH}.GeneratedCertificate")
    @patch(f"{COMMAND_MODULE_PATH}.use_read_replica_if_available")
    def test_get_certificates_queryset(self, mock_use_read_replica: Mock, mock_certificate_model: Mock):
        """Test getting certificates queryset."""
        mock_queryset = Mock()
        mock_use_read_replica.return_value = mock_queryset

        result = self.command.get_certificates_queryset(7)

        self.assertEqual(result, mock_queryset)
        mock_use_read_replica.assert_called_once()
        mock_certificate_model.objects.filter.assert_called_once()

    @patch.object(Command, "get_certificates_queryset")
    def test_process_service_success(self, mock_get_queryset: Mock):
        """Test successful processing of a service."""
        mock_get_queryset.return_value = [self.certificate1, self.certificate2]

        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "days": 10,
            "page_size": 500,
        }

        options = {"days": 7, "page_size": 100}

        self.command.process_service(service_config, options)

        mock_get_queryset.assert_called_once_with(7)
        command_output = self.command.stdout.getvalue()
        self.assertIn("Processing service: test_service", command_output)
        self.assertIn("Processing certificates from the last 7 days", command_output)
        self.assertIn("Page size: 100", command_output)
        self.assertIn("Total certificates to process: 2", command_output)

    @patch.object(Command, "get_certificates_queryset")
    def test_process_service_with_defaults(self, mock_get_queryset: Mock):
        """Test processing service with default values."""
        mock_get_queryset.return_value = []
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
        }
        options = {}

        self.command.process_service(service_config, options)

        command_output = self.command.stdout.getvalue()
        self.assertIn("Processing service: test_service", command_output)
        self.assertIn("Processing certificates from the last 7 days", command_output)
        self.assertIn("Page size: 1000", command_output)
        self.assertIn("Total certificates to process: 0", command_output)

    @patch("builtins.open", mock_open())
    def test_handle_success(self):
        """Test successful command execution."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(Command, "process_service") as mock_process:
                options = {
                    "config": "/fake/path/config.yml",
                    "dry_run": False,
                    "async_mode": False,
                }

                self.command.handle(**options)

                mock_process.assert_called_once()

    @patch("builtins.open", mock_open())
    def test_handle_dry_run(self):
        """Test command execution in dry run mode."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(Command, "process_service") as mock_process:
                options = {
                    "config": "/fake/path/config.yml",
                    "dry_run": True,
                    "async_mode": False,
                }

                self.command.handle(**options)

                self.assertTrue(self.command.dry_run)
                mock_process.assert_called_once()

    @patch("builtins.open", mock_open())
    def test_handle_async_mode(self):
        """Test command execution in async mode."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            options = {
                "config": "/fake/path/config.yml",
                "dry_run": False,
                "async_mode": True,
            }

            self.command.handle(**options)

            output = self.command.stdout.getvalue()
            self.assertIn("ASYNC MODE", output)

    @patch("builtins.open", mock_open())
    def test_handle_specific_service(self):
        """Test command execution with specific service name."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(Command, "process_service") as mock_process:
                options = {
                    "config": "/fake/path/config.yml",
                    "service_name": "test_service",
                    "dry_run": False,
                    "async_mode": False,
                }

                self.command.handle(**options)

                mock_process.assert_called_once()

    @patch("builtins.open", mock_open())
    def test_handle_service_not_found(self):
        """Test command execution with non-existent service name."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            options = {
                "config": "/fake/path/config.yml",
                "service_name": "nonexistent_service",
                "dry_run": False,
                "async_mode": False,
            }

            with self.assertRaises(CommandError) as context:
                self.command.handle(**options)

            self.assertIn("Service 'nonexistent_service' not found", str(context.exception))


class TestSendCertificatesByWebServiceCommandIntegration(TestCase):
    """
    Integration tests for the send_certificates_by_web_service command.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User()
        self.certificate = Certificate(self.user)

    @patch.object(Command, "get_certificates_queryset")
    @patch("requests.post")
    def test_full_command_execution(self, mock_post: Mock, mock_get_queryset: Mock):
        """Test full command execution with real configuration."""
        mock_get_queryset.return_value = [self.certificate]
        mock_response = Mock()
        mock_response.ok = True
        mock_post.return_value = mock_response

        config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "integration_test",
                    "endpoint_url": "https://api.test.com/certificates",
                    "auth_token": "test_token",
                    "auth_type": "bearer",
                    "days": 1,
                    "page_size": 10,
                    "fields": [
                        {
                            "name": "certificate_date",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.certificate.date",
                        },
                        {
                            "name": "student_email",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
                        },
                    ],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_config_file:
            yaml.dump(config, tmp_config_file)
            config_path = tmp_config_file.name

        try:
            command = Command()
            command.handle(
                config=config_path,
                service_name="integration_test",
                dry_run=False,
                verbosity=0,
            )
        finally:
            os.remove(config_path)

        expected_payload = [
            {
                "certificate_date": self.certificate.created_date.isoformat(),
                "student_email": self.user.email,
            }
        ]
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://api.test.com/certificates")
        self.assertEqual(call_args[1]["json"], expected_payload)
        self.assertIn("Authorization", call_args[1]["headers"])
