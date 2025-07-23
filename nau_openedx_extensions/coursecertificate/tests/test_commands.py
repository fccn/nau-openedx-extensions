"""
Tests for the send_certificates_by_web_service management command.
"""

import os
import tempfile
from io import StringIO
from unittest.mock import Mock, mock_open, patch

import yaml
from django.core.management.base import CommandError, OutputWrapper
from django.test import TestCase

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

        self.sample_config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "test_service",
                    "endpoint_url": "https://api.test.com/certificates",
                    "endpoint_timeout": 60,
                    "auth_token": "test_token",
                    "auth_type": "bearer",
                    "auth_header": "Authorization",
                    "days": 7,
                    "page_size": 100,
                    "fields": [
                        {
                            "name": "certificate_id",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.certificate_id",
                        },
                        {
                            "name": "student_email",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                        },
                        {
                            "name": "course_id",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.course_id",
                        },
                        {
                            "name": "hashed_email",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                            "trans": "md5",
                        },
                        {
                            "name": "encoded_course",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.course_code",
                            "trans": "base64",
                        },
                    ],
                    "filters": [
                        {
                            "func": "nau_openedx_extensions.coursecertificate.filters.certificate_by_org",
                            "args": ["NAU"],
                        },
                    ],
                }
            ]
        }

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

    def test_log_msg(self):
        """Test log message output."""
        test_message = "Test message"
        self.command.log_msg(test_message)

        output = self.command.stdout.getvalue()
        self.assertIn(test_message, output)

    def test_filter_services_no_target(self):
        """Test filtering services without target service."""
        config = self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"]
        result = self.command.filter_services(config, None)

        self.assertEqual(result, config)

    def test_filter_services_with_target(self):
        """Test filtering services with target service."""
        config = self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"]
        result = self.command.filter_services(config, "test_service")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["service_name"], "test_service")

    def test_filter_services_target_not_found(self):
        """Test filtering services when target service is not found."""
        config = self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"]

        with self.assertRaises(CommandError) as context:
            self.command.filter_services(config, "nonexistent_service")

        self.assertIn("Service 'nonexistent_service' not found", str(context.exception))

    def test_process_service_safely_success(self):
        """Test successful processing of a service safely."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
        }

        options = {"days": 7, "page_size": 100}

        with patch.object(self.command.engine, "process_service") as mock_process:
            result = self.command.process_service_safely(service_config, options)

            self.assertTrue(result)
            mock_process.assert_called_once_with(service_config, options)

            output = self.command.stdout.getvalue()
            self.assertIn("Successfully processed service: test_service", output)

    def test_process_service_safely_key_error(self):
        """Test processing service safely with key error."""
        service_config = {
            "service_name": "test_service",
        }

        options = {"days": 7, "page_size": 100}

        with patch.object(self.command.engine, "process_service") as mock_process:
            mock_process.side_effect = KeyError("missing_key")

            result = self.command.process_service_safely(service_config, options)

            self.assertFalse(result)
            output = self.command.stdout.getvalue()
            self.assertIn("Configuration error for service test_service", output)

    def test_process_service_safely_value_error(self):
        """Test processing service safely with value error."""
        service_config = {
            "service_name": "test_service",
        }

        options = {"days": 7, "page_size": 100}

        with patch.object(self.command.engine, "process_service") as mock_process:
            mock_process.side_effect = ValueError("invalid_value")

            result = self.command.process_service_safely(service_config, options)

            self.assertFalse(result)
            output = self.command.stdout.getvalue()
            self.assertIn("Configuration error for service test_service", output)

    def test_process_service_safely_unexpected_error(self):
        """Test processing service safely with unexpected error."""
        service_config = {
            "service_name": "test_service",
        }

        options = {"days": 7, "page_size": 100}

        with patch.object(self.command.engine, "process_service") as mock_process:
            mock_process.side_effect = Exception("unexpected_error")

            result = self.command.process_service_safely(service_config, options)

            self.assertFalse(result)
            output = self.command.stdout.getvalue()
            self.assertIn("Unexpected error processing service test_service", output)

    @patch("builtins.open", mock_open())
    def test_handle_success(self):
        """Test successful command execution."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(self.command, "process_service_safely", return_value=True) as mock_process:
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
            with patch.object(self.command, "process_service_safely", return_value=True) as mock_process:
                options = {
                    "config": "/fake/path/config.yml",
                    "dry_run": True,
                    "async_mode": False,
                }

                self.command.handle(**options)

                mock_process.assert_called_once()
                call_args = mock_process.call_args
                options_passed = call_args[0][1]
                self.assertTrue(options_passed.get("dry_run", False))

                output = self.command.stdout.getvalue()
                self.assertIn("=== DRY RUN MODE - No actual requests will be sent ===", output)

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

            with self.assertRaises(CommandError) as context:
                self.command.handle(**options)

            self.assertIn("Async mode is not yet implemented", str(context.exception))

    @patch("builtins.open", mock_open())
    def test_handle_specific_service(self):
        """Test command execution with specific service name."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(self.command, "process_service_safely", return_value=True) as mock_process:
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

    def test_handle_sync_success(self):
        """Test successful sync handle execution."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(
                self.command, "load_config", return_value=self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"]
            ) as mock_load_config:
                with patch.object(self.command, "process_service_safely", return_value=True) as mock_process:
                    options = {
                        "config": "/fake/path/config.yml",
                        "dry_run": False,
                    }

                    self.command.handle_sync(options)

                    mock_load_config.assert_called_once_with("/fake/path/config.yml")
                    mock_process.assert_called_once()

    def test_handle_sync_with_failure(self):
        """Test sync handle execution with service failure."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(
                self.command, "load_config", return_value=self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"]
            ) as mock_load_config:
                with patch.object(self.command, "process_service_safely", return_value=False) as mock_process:
                    options = {
                        "config": "/fake/path/config.yml",
                        "dry_run": False,
                    }

                    self.command.handle_sync(options)

                    mock_load_config.assert_called_once_with("/fake/path/config.yml")
                    mock_process.assert_called_once()

                    output = self.command.stdout.getvalue()
                    self.assertIn("Successfully processed 0/1 services", output)

    def test_handle_async_raises_error(self):
        """Test that async mode raises CommandError."""
        options = {}

        with self.assertRaises(CommandError) as context:
            self.command.handle_async(options)

        self.assertIn("Async mode is not yet implemented", str(context.exception))

    def test_load_config_with_endpoint_timeout(self):
        """Test loading configuration with endpoint_timeout setting."""
        config_with_timeout = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "test_service",
                    "endpoint_url": "https://api.test.com/certificates",
                    "endpoint_timeout": 120,
                    "auth_token": "test_token",
                    "auth_type": "bearer",
                }
            ]
        }
        config_yaml = yaml.dump(config_with_timeout)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_service")
        self.assertEqual(config[0]["endpoint_timeout"], 120)

    def test_load_config_without_endpoint_timeout(self):
        """Test loading configuration without endpoint_timeout setting."""
        config_without_timeout = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "test_service",
                    "endpoint_url": "https://api.test.com/certificates",
                    "auth_token": "test_token",
                    "auth_type": "bearer",
                }
            ]
        }
        config_yaml = yaml.dump(config_without_timeout)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_service")
        self.assertNotIn("endpoint_timeout", config[0])

    def test_integration_with_endpoint_timeout(self):
        """Test integration passes endpoint_timeout to engine."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "endpoint_timeout": 180,
        }
        options = {"days": 7, "page_size": 100}

        with patch.object(self.command.engine, "process_service") as mock_process:
            self.command.process_service_safely(service_config, options)

            mock_process.assert_called_once_with(service_config, options)
            # Verify that the service config with endpoint_timeout was passed
            call_args = mock_process.call_args
            passed_service_config = call_args[0][0]
            self.assertEqual(passed_service_config["endpoint_timeout"], 180)


class TestSendCertificatesByWebServiceCommandIntegration(TestCase):
    """
    Integration tests for the send_certificates_by_web_service command.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User()
        self.certificate = Certificate(self.user)

    @patch.object(Command, "process_service_safely")
    def test_full_command_execution(self, mock_process_service_safely: Mock):
        """Test full command execution with real configuration."""
        mock_process_service_safely.return_value = True

        config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "integration_test",
                    "endpoint_url": "https://api.test.com/certificates",
                    "endpoint_timeout": 90,
                    "auth_token": "test_token",
                    "auth_type": "bearer",
                    "days": 1,
                    "page_size": 10,
                    "fields": [
                        {
                            "name": "certificate_date",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.certificate_date",
                        },
                        {
                            "name": "student_email",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
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

        mock_process_service_safely.assert_called_once()
        call_args = mock_process_service_safely.call_args
        service_config = call_args[0][0]
        options = call_args[0][1]

        self.assertEqual(service_config["service_name"], "integration_test")
        self.assertEqual(service_config["endpoint_url"], "https://api.test.com/certificates")
        self.assertEqual(service_config["endpoint_timeout"], 90)
        self.assertEqual(options["dry_run"], False)
