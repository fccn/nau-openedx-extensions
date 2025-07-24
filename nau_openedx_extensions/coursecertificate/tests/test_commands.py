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
                },
                {
                    "service_name": "test_service_2",
                    "endpoint_url": "https://api2.test.com/certificates",
                    "endpoint_timeout": 30,
                    "auth_token": "test_token_2",
                    "auth_type": "bearer",
                    "auth_header": "Authorization",
                    "days": 3,
                    "page_size": 50,
                    "fields": [],
                    "filters": [],
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

        self.assertEqual(len(config), 2)
        self.assertEqual(config[0]["service_name"], "test_service")
        self.assertEqual(config[0]["endpoint_url"], "https://api.test.com/certificates")
        self.assertEqual(config[1]["service_name"], "test_service_2")
        self.assertEqual(config[1]["endpoint_url"], "https://api2.test.com/certificates")

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

                self.assertEqual(mock_process.call_count, 2)

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

                self.assertEqual(mock_process.call_count, 2)
                call_args = mock_process.call_args
                options_passed = call_args[0][1]
                self.assertTrue(options_passed.get("dry_run", False))

                output = self.command.stdout.getvalue()
                self.assertIn("=== DRY RUN MODE - No actual requests will be sent ===", output)

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

    @patch("builtins.open", mock_open())
    def test_handle_with_certificate_id(self):
        """Test command execution with specific certificate ID."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(self.command, "process_service_safely", return_value=True) as mock_process:
                options = {
                    "config": "/fake/path/config.yml",
                    "certificate_id": 123,
                    "dry_run": False,
                    "async_mode": False,
                }

                self.command.handle(**options)

                self.assertEqual(mock_process.call_count, 2)
                call_args = mock_process.call_args
                options_passed = call_args[0][1]
                self.assertEqual(options_passed.get("certificate_id"), 123)

    @patch("builtins.open", mock_open())
    def test_handle_with_certificate_id_and_service_name(self):
        """Test command execution with both certificate ID and service name."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(self.command, "process_service_safely", return_value=True) as mock_process:
                options = {
                    "config": "/fake/path/config.yml",
                    "certificate_id": 456,
                    "service_name": "test_service",
                    "dry_run": False,
                    "async_mode": False,
                }

                self.command.handle(**options)

                mock_process.assert_called_once()
                call_args = mock_process.call_args
                options_passed = call_args[0][1]
                self.assertEqual(options_passed.get("certificate_id"), 456)
                self.assertEqual(options_passed.get("service_name"), "test_service")

    @patch("builtins.open", mock_open())
    def test_handle_with_certificate_id_and_dry_run(self):
        """Test command execution with certificate ID in dry run mode."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(self.command, "process_service_safely", return_value=True) as mock_process:
                options = {
                    "config": "/fake/path/config.yml",
                    "certificate_id": 789,
                    "dry_run": True,
                    "async_mode": False,
                }

                self.command.handle(**options)

                self.assertEqual(mock_process.call_count, 2)
                call_args = mock_process.call_args
                options_passed = call_args[0][1]
                self.assertEqual(options_passed.get("certificate_id"), 789)
                self.assertTrue(options_passed.get("dry_run", False))

                output = self.command.stdout.getvalue()
                self.assertIn("=== DRY RUN MODE - No actual requests will be sent ===", output)

    def test_process_service_safely_with_certificate_id(self):
        """Test processing service safely with certificate ID option."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
        }

        options = {"days": 7, "page_size": 100, "certificate_id": 999}

        with patch.object(self.command.engine, "process_service") as mock_process:
            result = self.command.process_service_safely(service_config, options)

            self.assertTrue(result)
            mock_process.assert_called_once_with(service_config, options)

            call_args = mock_process.call_args
            options_passed = call_args[0][1]
            self.assertEqual(options_passed.get("certificate_id"), 999)

            output = self.command.stdout.getvalue()
            self.assertIn("Successfully processed service: test_service", output)

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
                    self.assertEqual(mock_process.call_count, 2)

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
                    self.assertEqual(mock_process.call_count, 2)
                    output = self.command.stdout.getvalue()
                    self.assertIn("Successfully processed 0/2 services", output)

    def test_handle_sync_with_certificate_id(self):
        """Test sync handle execution with certificate ID."""
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with patch.object(
                self.command, "load_config", return_value=self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"]
            ) as mock_load_config:
                with patch.object(self.command, "process_service_safely", return_value=True) as mock_process:
                    options = {
                        "config": "/fake/path/config.yml",
                        "certificate_id": 1234,
                        "dry_run": False,
                    }

                    self.command.handle_sync(options)

                    mock_load_config.assert_called_once_with("/fake/path/config.yml")
                    self.assertEqual(mock_process.call_count, 2)

                    call_args = mock_process.call_args
                    options_passed = call_args[0][1]
                    self.assertEqual(options_passed.get("certificate_id"), 1234)

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
            call_args = mock_process.call_args
            passed_service_config = call_args[0][0]
            self.assertEqual(passed_service_config["endpoint_timeout"], 180)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_handle_async_basic(self, mock_task):
        """Test basic async mode functionality."""

        mock_task.delay.return_value = Mock(id="task-123")
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            self.command.handle_async({"config": "/fake/path/config.yml"})

        self.assertEqual(mock_task.delay.call_count, 2)
        output = self.command.stdout.getvalue()
        self.assertIn("Dispatching 2 service(s) to Celery", output)
        self.assertIn("Successfully dispatched: 2/2 tasks", output)
        self.assertIn("task-123", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_handle_async_with_service_filter(self, mock_task):
        """Test async mode with specific service filter."""

        mock_task.delay.return_value = Mock(id="task-456")
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            self.command.handle_async({"config": "/fake/path/config.yml", "service_name": "test_service"})

        self.assertEqual(mock_task.delay.call_count, 1)
        args, kwargs = mock_task.delay.call_args
        self.assertEqual(args[0]["service_name"], "test_service")

        output = self.command.stdout.getvalue()
        self.assertIn("Dispatching 1 service(s) to Celery", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_handle_async_dispatch_failure(self, mock_task):
        """Test async mode when task dispatch fails."""

        mock_task.delay.side_effect = ConnectionError("Redis connection failed")
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            self.command.handle_async({"config": "/fake/path/config.yml"})

        output = self.command.stdout.getvalue()
        self.assertIn("Failed to dispatch task", output)
        self.assertIn("Redis connection failed", output)
        self.assertIn("Successfully dispatched: 0/2 tasks", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_handle_async_partial_failure(self, mock_task):
        """Test async mode when some dispatches fail."""

        mock_task.delay.side_effect = [Mock(id="task-success"), ValueError("Invalid config")]
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            self.command.handle_async({"config": "/fake/path/config.yml"})

        output = self.command.stdout.getvalue()
        self.assertIn("Successfully dispatched: 1/2 tasks", output)
        self.assertIn("Failed to dispatch: 1 tasks", output)
        self.assertIn("task-success", output)

    def test_handle_async_invalid_service_name(self):
        """Test async mode with invalid service name."""

        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            with self.assertRaises(CommandError) as context:
                self.command.handle_async({"config": "/fake/path/config.yml", "service_name": "nonexistent_service"})

        self.assertIn("Service 'nonexistent_service' not found", str(context.exception))

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_dispatch_service_task_safely_success(self, mock_task):
        """Test successful task dispatch."""

        mock_task.delay.return_value = Mock(id="task-789")
        service_config = self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"][0]

        result = self.command.dispatch_service_task_safely(service_config, {"dry_run": False})

        self.assertIsNotNone(result)
        self.assertEqual(result["service_name"], "test_service")
        self.assertEqual(result["task_id"], "task-789")

        output = self.command.stdout.getvalue()
        self.assertIn("Task dispatched for service 'test_service'", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_dispatch_service_task_safely_connection_error(self, mock_task):
        """Test task dispatch with connection error."""

        mock_task.delay.side_effect = ConnectionError("Broker connection failed")
        service_config = self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"][0]

        result = self.command.dispatch_service_task_safely(service_config, {"dry_run": False})

        self.assertIsNone(result)
        output = self.command.stdout.getvalue()
        self.assertIn("Failed to dispatch task for service 'test_service'", output)
        self.assertIn("Broker connection failed", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_dispatch_service_task_safely_value_error(self, mock_task):
        """Test task dispatch with value error."""

        mock_task.delay.side_effect = ValueError("Invalid configuration")
        service_config = self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"][0]

        result = self.command.dispatch_service_task_safely(service_config, {"dry_run": False})

        self.assertIsNone(result)
        output = self.command.stdout.getvalue()
        self.assertIn("Failed to dispatch task for service 'test_service'", output)
        self.assertIn("Invalid configuration", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_dispatch_service_task_safely_unexpected_error(self, mock_task):
        """Test task dispatch with unexpected error."""

        mock_task.delay.side_effect = RuntimeError("Unexpected error")
        service_config = self.sample_config["NAU_SEND_COURSE_CERTIFICATE_CONFIG"][0]

        result = self.command.dispatch_service_task_safely(service_config, {"dry_run": False})

        self.assertIsNone(result)
        output = self.command.stdout.getvalue()
        self.assertIn("Unexpected error dispatching task for service 'test_service'", output)
        self.assertIn("Unexpected error", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_dispatch_service_task_safely_unknown_service(self, mock_task):
        """Test task dispatch with missing service name."""

        mock_task.delay.return_value = Mock(id="task-unknown")
        service_config = {"base_url": "https://test.com"}  # Missing service_name

        result = self.command.dispatch_service_task_safely(service_config, {"dry_run": False})

        self.assertIsNotNone(result)
        self.assertEqual(result["service_name"], "unknown")

        output = self.command.stdout.getvalue()
        self.assertIn("Task dispatched for service 'unknown'", output)

    def test_integration_with_certificate_id(self):
        """Test integration passes certificate_id to engine."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
        }
        options = {"days": 7, "page_size": 100, "certificate_id": 555}

        with patch.object(self.command.engine, "process_service") as mock_process:
            self.command.process_service_safely(service_config, options)

            mock_process.assert_called_once_with(service_config, options)
            # Verify that the options with certificate_id were passed
            call_args = mock_process.call_args
            passed_options = call_args[0][1]
            self.assertEqual(passed_options["certificate_id"], 555)


class TestSendCertificatesByWebServiceCommandIntegration(TestCase):
    """
    Integration tests for the send_certificates_by_web_service command.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User()
        self.certificate = Certificate(self.user)
        self.command = Command()
        self.command.stdout = OutputWrapper(StringIO())
        self.command.stderr = OutputWrapper(StringIO())

        self.sample_config = {
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

    @patch.object(Command, "process_service_safely")
    def test_full_command_execution(self, mock_process_service_safely: Mock):
        """Test full command execution with real configuration."""
        mock_process_service_safely.return_value = True

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_config_file:
            yaml.dump(self.sample_config, tmp_config_file)
            config_path = tmp_config_file.name

        try:
            self.command.handle(
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

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_command_async_mode_integration(self, mock_task):
        """Test command async mode integration."""

        mock_task.delay.return_value = Mock(id="integration-task")
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            self.command.handle(async_mode=True, config="/fake/path/config.yml")

            mock_task.delay.assert_called_once()
            output = self.command.stdout.getvalue()
            self.assertIn("ASYNC MODE", output)
            self.assertIn("integration-task", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_command_async_dry_run_integration(self, mock_task):
        """Test command async + dry-run mode integration."""

        mock_task.delay.return_value = Mock(id="dry-run-task")
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            self.command.handle(async_mode=True, dry_run=True, config="/fake/path/config.yml")

            mock_task.delay.assert_called_once()
            args, kwargs = mock_task.delay.call_args
            self.assertTrue(args[1]["dry_run"])

            output = self.command.stdout.getvalue()
            self.assertIn("ASYNC MODE", output)
            self.assertIn("DRY RUN MODE", output)

    @patch(f"{COMMAND_MODULE_PATH}.process_service_certificates")
    def test_command_async_with_service_filter_integration(self, mock_task):
        """Test command async mode with service filter integration."""

        mock_task.delay.return_value = Mock(id="filtered-task")
        config_yaml = yaml.dump(self.sample_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            self.command.handle(async_mode=True, service_name="integration_test", config="/fake/path/config.yml")

            mock_task.delay.assert_called_once()
            args, kwargs = mock_task.delay.call_args
            self.assertEqual(args[0]["service_name"], "integration_test")

    @patch.object(Command, "process_service_safely")
    def test_full_command_execution_with_certificate_id(self, mock_process_service_safely: Mock):
        """Test full command execution with certificate ID."""
        mock_process_service_safely.return_value = True

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_config_file:
            yaml.dump(self.sample_config, tmp_config_file)
            config_path = tmp_config_file.name

        try:
            self.command.handle(
                config=config_path,
                service_name="integration_test",
                certificate_id=777,
                dry_run=True,
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
        self.assertEqual(options["certificate_id"], 777)
        self.assertEqual(options["dry_run"], True)
