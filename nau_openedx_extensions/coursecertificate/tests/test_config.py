"""
Tests for the coursecertificate configuration structure and validation.

This module tests the configuration loaded from config.yml to ensure
it follows the expected structure and contains valid values.
"""

import os
from unittest.mock import mock_open, patch

import yaml
from django.core.management.base import CommandError
from django.test import TestCase

from nau_openedx_extensions.coursecertificate.management.commands.send_certificates_by_web_service import Command


class TestConfigurationStructure(TestCase):
    """
    Test the configuration structure and validation.
    """

    def setUp(self):
        """Set up test data and configuration samples."""
        self.command = Command()

        # Minimal valid configuration
        self.minimal_config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "test_service",
                    "endpoint_url": "https://api.test.com/certificates",
                }
            ]
        }

        # Complete valid configuration
        self.complete_config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "complete_service",
                    "endpoint_url": "https://api.complete.com/certificates",
                    "endpoint_timeout": 30,
                    "auth_token": "test_auth_token",
                    "auth_type": "bearer",
                    "auth_header": "Authorization",
                    "page_size": 100,
                    "days": 30,
                    "fields": [
                        {"name": "email", "func": "nau_openedx_extensions.coursecertificate.extractors.student.email"},
                        {
                            "name": "hashed_email",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.student.email",
                            "trans": "md5",
                        },
                        {
                            "name": "nif",
                            "func": "nau_openedx_extensions.coursecertificate."
                            "extractors.student.nau_user_extended_model_field",
                            "args": "nif",
                        },
                    ],
                    "filters": [
                        {
                            "func": "nau_openedx_extensions.coursecertificate.filters.certificate_by_org",
                            "args": "TestOrg",
                        }
                    ],
                }
            ]
        }

        # Multiple services configuration
        self.multi_service_config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "service_one",
                    "endpoint_url": "https://api.one.com/certificates",
                    "endpoint_timeout": 60,
                    "auth_type": "bearer",
                    "page_size": 50,
                    "days": 7,
                },
                {
                    "service_name": "service_two",
                    "endpoint_url": "https://api.two.com/certificates",
                    "endpoint_timeout": 120,
                    "auth_type": "api_key",
                    "page_size": 200,
                    "days": 14,
                },
            ]
        }

    def test_load_minimal_valid_config(self):
        """Test loading a minimal valid configuration."""
        config_yaml = yaml.dump(self.minimal_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_service")
        self.assertEqual(config[0]["endpoint_url"], "https://api.test.com/certificates")
        self.assertNotIn("endpoint_timeout", config[0])

    def test_minimal_config_with_endpoint_timeout(self):
        """Test loading minimal configuration with endpoint_timeout."""
        minimal_with_timeout = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "test_service_with_timeout",
                    "endpoint_url": "https://api.test.com/certificates",
                    "endpoint_timeout": 45,
                }
            ]
        }

        config_yaml = yaml.dump(minimal_with_timeout)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_service_with_timeout")
        self.assertEqual(config[0]["endpoint_url"], "https://api.test.com/certificates")
        self.assertEqual(config[0]["endpoint_timeout"], 45)

    def test_load_complete_valid_config(self):
        """Test loading a complete valid configuration."""
        config_yaml = yaml.dump(self.complete_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 1)
        service = config[0]
        self.assertEqual(service["service_name"], "complete_service")
        self.assertEqual(service["endpoint_url"], "https://api.complete.com/certificates")
        self.assertEqual(service["endpoint_timeout"], 30)
        self.assertEqual(service["auth_token"], "test_auth_token")
        self.assertEqual(service["auth_type"], "bearer")
        self.assertEqual(service["auth_header"], "Authorization")
        self.assertEqual(service["page_size"], 100)
        self.assertEqual(service["days"], 30)
        self.assertEqual(len(service["fields"]), 3)
        self.assertEqual(len(service["filters"]), 1)

    def test_load_multiple_services_config(self):
        """Test loading configuration with multiple services."""
        config_yaml = yaml.dump(self.multi_service_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 2)
        self.assertEqual(config[0]["service_name"], "service_one")
        self.assertEqual(config[1]["service_name"], "service_two")
        self.assertEqual(config[0]["page_size"], 50)
        self.assertEqual(config[1]["page_size"], 200)
        self.assertEqual(config[0]["endpoint_timeout"], 60)
        self.assertEqual(config[1]["endpoint_timeout"], 120)

    def test_load_empty_config(self):
        """Test loading empty configuration."""
        empty_config = {"NAU_SEND_COURSE_CERTIFICATE_CONFIG": []}
        config_yaml = yaml.dump(empty_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 0)

    def test_load_config_missing_root_key(self):
        """Test loading configuration without the root key."""
        invalid_config = {"SOME_OTHER_CONFIG": []}
        config_yaml = yaml.dump(invalid_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 0)

    def test_load_config_null_root_key(self):
        """Test loading configuration with null root key."""
        invalid_config = {"NAU_SEND_COURSE_CERTIFICATE_CONFIG": None}
        config_yaml = yaml.dump(invalid_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertIsNone(config)


class TestConfigurationValidation(TestCase):
    """
    Test configuration validation and error handling.
    """

    def setUp(self):
        """Set up test data."""
        self.command = Command()

    def test_invalid_yaml_syntax(self):
        """Test handling of invalid YAML syntax."""
        invalid_yaml = """
        NAU_SEND_COURSE_CERTIFICATE_CONFIG:
          - service_name: test
            endpoint_url: https://api.test.com
            fields:
              - name: email
                func: student.email
                # Missing closing bracket
        [
        """

        with patch("builtins.open", mock_open(read_data=invalid_yaml)):
            with self.assertRaises(CommandError) as context:
                self.command.load_config("/fake/path/config.yml")

            self.assertIn("Error parsing YAML configuration", str(context.exception))

    def test_yaml_with_wrong_structure(self):
        """Test handling of YAML with wrong structure."""
        wrong_structure = """
        NAU_SEND_COURSE_CERTIFICATE_CONFIG: "this should be a list"
        """

        with patch("builtins.open", mock_open(read_data=wrong_structure)):
            # This should not raise an exception but should return empty or handle gracefully
            config = self.command.load_config("/fake/path/config.yml")
            # The actual behavior depends on implementation, but it should not crash
            self.assertIsNotNone(config)


class TestRealConfigurationFile(TestCase):
    """
    Test the actual config.yml file in the project.
    """

    def setUp(self):
        """Set up test data."""
        self.command = Command()
        self.config_path = self.command.get_default_config_path()

    def test_config_file_exists(self):
        """Test that the config.yml file exists."""
        self.assertTrue(os.path.exists(self.config_path), f"Config file should exist at {self.config_path}")

    def test_config_file_is_valid_yaml(self):
        """Test that the config.yml file contains valid YAML."""
        if os.path.exists(self.config_path):
            try:
                config = self.command.load_config(self.config_path)
                self.assertIsInstance(config, list)
            except CommandError as e:
                self.fail(f"Config file contains invalid YAML: {e}")

    def test_config_file_has_valid_structure(self):
        """Test that the config.yml file has valid structure."""
        if os.path.exists(self.config_path):
            config = self.command.load_config(self.config_path)

            # Should be a list
            self.assertIsInstance(config, list)

            # Each service should have required fields
            for i, service in enumerate(config):
                with self.subTest(service_index=i):
                    self.assertIsInstance(service, dict)
                    self.assertIn("service_name", service)
                    self.assertIn("endpoint_url", service)

                    # Check optional fields if present
                    if "fields" in service:
                        self.assertIsInstance(service["fields"], list)
                        for field in service["fields"]:
                            self.assertIn("name", field)
                            self.assertIn("func", field)

                    if "filters" in service:
                        self.assertIsInstance(service["filters"], list)
                        for filter_config in service["filters"]:
                            self.assertIn("func", filter_config)


class TestConfigurationEdgeCases(TestCase):
    """
    Test edge cases and unusual configurations.
    """

    def setUp(self):
        """Set up test data."""
        self.command = Command()

    def test_config_with_unicode_characters(self):
        """Test configuration with unicode characters."""
        unicode_config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "test_unicode_üñíçödé",
                    "endpoint_url": "https://api.test.com/certificates",
                    "fields": [
                        {
                            "name": "nome_português",
                            "func": "nau_openedx_extensions.coursecertificate.extractors.student.name",
                        }
                    ],
                }
            ]
        }

        config_yaml = yaml.dump(unicode_config, allow_unicode=True)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_unicode_üñíçödé")

    def test_config_with_very_long_values(self):
        """Test configuration with very long string values."""
        long_value = "x" * 1000
        long_config = {
            "NAU_SEND_COURSE_CERTIFICATE_CONFIG": [
                {
                    "service_name": "long_test",
                    "endpoint_url": f"https://very-long-domain-name-{long_value}.com/api/certificates",
                    "auth_token": long_value,
                }
            ]
        }

        config_yaml = yaml.dump(long_config)

        with patch("builtins.open", mock_open(read_data=config_yaml)):
            config = self.command.load_config("/fake/path/config.yml")

        self.assertEqual(len(config), 1)
        self.assertEqual(len(config[0]["auth_token"]), 1000)


class TestCurrentConfigurationContent(TestCase):
    """
    Test the current content and configuration of the real `config.yml` file.
    These tests validate any services and their configurations generically.
    """

    def setUp(self):
        """Set up test data."""
        self.command = Command()
        self.config_path = self.command.get_default_config_path()

        # Load the actual configuration if file exists
        if os.path.exists(self.config_path):
            self.config = self.command.load_config(self.config_path)
        else:
            self.config = []

    def test_config_has_services(self):
        """Test that the configuration contains at least one service."""
        if not self.config:
            self.skipTest("Config file not found")

        self.assertGreater(len(self.config), 0, "Configuration should have at least one service")

    def test_all_services_have_required_fields(self):
        """Test that all services have the minimum required fields."""
        if not self.config:
            self.skipTest("Config file not found")

        required_fields = ["service_name", "endpoint_url"]

        for i, service in enumerate(self.config):
            with self.subTest(service_index=i, service_name=service.get("service_name", f"service_{i}")):
                self.assertIsInstance(service, dict, f"Service {i} should be a dictionary")

                for required_field in required_fields:
                    self.assertIn(required_field, service, f"Service {i} should have required field '{required_field}'")
                    self.assertIsNotNone(
                        service[required_field], f"Service {i} field '{required_field}' should not be None"
                    )
                    self.assertNotEqual(
                        service[required_field], "", f"Service {i} field '{required_field}' should not be empty"
                    )

    def test_all_services_have_valid_structure(self):
        """Test that all services have valid structure for their fields."""
        if not self.config:
            self.skipTest("Config file not found")

        for i, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{i}")

            with self.subTest(service=service_name):
                endpoint_url = service.get("endpoint_url")
                if endpoint_url:
                    self.assertIsInstance(
                        endpoint_url, str, f"The 'endpoint_url' in {service_name} service should be a string"
                    )
                    self.assertTrue(
                        endpoint_url.startswith(("http://", "https://")),
                        f"The 'endpoint_url' in {service_name} service should be a valid URL",
                    )

                auth_type = service.get("auth_type")
                if auth_type:
                    self.assertIsInstance(
                        auth_type, str, f"The 'auth_type' in {service_name} service should be a string"
                    )

                auth_header = service.get("auth_header")
                if auth_header:
                    self.assertIsInstance(
                        auth_header, str, f"The 'auth_header' in {service_name} service should be a string"
                    )

                auth_token = service.get("auth_token")
                if auth_token:
                    self.assertIsInstance(
                        auth_token, str, f"The 'auth_token' in {service_name} service should be a string"
                    )

                # Test numeric fields if present
                page_size = service.get("page_size")
                if page_size is not None:
                    self.assertIsInstance(
                        page_size, int, f"The 'page_size' in {service_name} service should be an integer"
                    )
                    self.assertGreater(page_size, 0, f"The 'page_size' in {service_name} service should be positive")

                # Test days field if present
                days = service.get("days")
                if days is not None:
                    self.assertIsInstance(days, int, f"The 'days' in {service_name} service should be an integer")
                    self.assertGreater(days, 0, f"The 'days' in {service_name} service should be positive")

                # Test endpoint_timeout if present
                endpoint_timeout = service.get("endpoint_timeout")
                if endpoint_timeout is not None:
                    self.assertIsInstance(
                        endpoint_timeout, int, f"The 'endpoint_timeout' in {service_name} service should be an integer"
                    )
                    self.assertGreater(
                        endpoint_timeout, 0, f"The 'endpoint_timeout' in {service_name} service should be positive"
                    )

                # Test fields structure if present
                fields = service.get("fields")
                if fields is not None:
                    self.assertIsInstance(fields, list, "fields should be a list")
                    for j, field in enumerate(fields):
                        self.assertIsInstance(field, dict, f"Field {j} should be a dictionary")
                        self.assertIn("name", field, f"Field {j} should have 'name'")
                        self.assertIn("func", field, f"Field {j} should have 'func'")

                # Test filters structure if present
                filters = service.get("filters")
                if filters is not None:
                    self.assertIsInstance(filters, list, "filters should be a list")
                    for j, filter_config in enumerate(filters):
                        self.assertIsInstance(filter_config, dict, f"Filter {j} should be a dictionary")
                        self.assertIn("func", filter_config, f"Filter {j} should have 'func'")

    def test_all_fields_have_valid_extractors(self):
        """Test that all fields reference valid extractor functions."""
        if not self.config:
            self.skipTest("Config file not found")

        for i, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{i}")
            fields = service.get("fields", [])

            for j, field in enumerate(fields):
                field_name = field.get("name", f"field_{j}")
                func_path = field.get("func")

                with self.subTest(service=service_name, field=field_name):
                    self.assertIsNotNone(func_path, f"Field '{field_name}' should have a 'func' defined")
                    self.assertIsInstance(func_path, str, f"Field '{field_name}' func should be a string")
                    self.assertIn(".", func_path, f"Field '{field_name}' func should be a module path")

                    # Check that it looks like a valid extractor path
                    if "extractors" in func_path:
                        self.assertTrue(
                            func_path.startswith("nau_openedx_extensions.coursecertificate.extractors"),
                            f"Extractor '{func_path}' should start with the correct module path",
                        )

    def test_all_filters_have_valid_functions(self):
        """Test that all filters reference valid filter functions."""
        if not self.config:
            self.skipTest("Config file not found")

        for i, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{i}")
            filters = service.get("filters", [])

            for j, filter_config in enumerate(filters):
                func_path = filter_config.get("func")

                with self.subTest(service=service_name, filter_index=j):
                    self.assertIsNotNone(func_path, f"Filter {j} should have a 'func' defined")
                    self.assertIsInstance(func_path, str, f"Filter {j} func should be a string")
                    self.assertIn(".", func_path, f"Filter {j} func should be a module path")

                    # Check that it looks like a valid filter path
                    if "filters" in func_path:
                        self.assertTrue(
                            func_path.startswith("nau_openedx_extensions.coursecertificate.filters"),
                            f"Filter '{func_path}' should start with the correct module path",
                        )

    def test_extractor_functions_are_importable(self):
        """Test that all extractor functions referenced in config can be imported."""
        if not self.config:
            self.skipTest("Config file not found")

        for service_idx, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{service_idx}")
            fields = service.get("fields", [])

            for field in fields:
                func_path = field.get("func")
                if func_path:
                    with self.subTest(service=service_name, field=field.get("name"), func=func_path):
                        try:
                            # Try to import the function
                            module_path, func_name = func_path.rsplit(".", 1)
                            module = __import__(module_path, fromlist=[func_name])
                            func = getattr(module, func_name)
                            self.assertTrue(callable(func), f"Function {func_path} should be callable")
                        except (ImportError, AttributeError) as e:
                            self.fail(f"Could not import extractor function {func_path}: {e}")

    def test_filter_functions_are_importable(self):
        """Test that all filter functions referenced in config can be imported."""
        if not self.config:
            self.skipTest("Config file not found")

        for service_idx, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{service_idx}")
            filters = service.get("filters", [])

            for filter_idx, filter_config in enumerate(filters):
                func_path = filter_config.get("func")
                if func_path:
                    with self.subTest(service=service_name, filter_idx=filter_idx, func=func_path):
                        try:
                            # Try to import the function
                            module_path, func_name = func_path.rsplit(".", 1)
                            module = __import__(module_path, fromlist=[func_name])
                            func = getattr(module, func_name)
                            self.assertTrue(callable(func), f"Function {func_path} should be callable")
                        except (ImportError, AttributeError) as e:
                            self.fail(f"Could not import filter function {func_path}: {e}")

    def test_field_transformations_are_valid(self):
        """Test that all transformations used in fields are supported."""
        if not self.config:
            self.skipTest("Config file not found")

        supported_transformations = ["md5", "base64"]

        for service_idx, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{service_idx}")
            fields = service.get("fields", [])

            for field in fields:
                trans = field.get("trans")
                if trans:
                    with self.subTest(service=service_name, field=field.get("name"), transformation=trans):
                        self.assertIn(trans, supported_transformations, f"Transformation '{trans}' is not supported")

    def test_service_configurations_are_reasonable(self):
        """Test that service configuration values are reasonable."""
        if not self.config:
            self.skipTest("Config file not found")

        for service_idx, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{service_idx}")

            with self.subTest(service=service_name):
                # Check page_size is reasonable
                page_size = service.get("page_size")
                if page_size is not None:
                    self.assertIsInstance(
                        page_size, int, f"The 'page_size' in {service_name} service should be an integer"
                    )
                    self.assertGreater(page_size, 0, f"The 'page_size' in {service_name} service should be positive")
                    self.assertLessEqual(
                        page_size, 10000, f"The 'page_size' in {service_name} service should not be excessively large"
                    )

                # Check days is reasonable
                days = service.get("days")
                if days is not None:
                    self.assertIsInstance(days, int, f"The 'days' in {service_name} service should be an integer")
                    self.assertGreater(days, 0, f"The 'days' in {service_name} service should be positive")
                    self.assertLessEqual(days, 365, f"The 'days' in {service_name} service should not exceed a year")

                # Check endpoint_timeout is reasonable
                endpoint_timeout = service.get("endpoint_timeout")
                if endpoint_timeout is not None:
                    self.assertIsInstance(
                        endpoint_timeout, int, f"The 'endpoint_timeout' in {service_name} service should be an integer"
                    )
                    self.assertGreater(
                        endpoint_timeout, 0, f"The 'endpoint_timeout' in {service_name} service should be positive"
                    )
                    self.assertLessEqual(
                        endpoint_timeout,
                        3600,
                        f"The 'endpoint_timeout' in {service_name} service should not exceed 1 hour (3600 seconds)",
                    )

                # Check service name is not empty
                self.assertIsInstance(
                    service_name, str, f"The 'service_name' in {service_name} service should be a string"
                )
                self.assertGreater(
                    len(service_name), 0, f"The 'service_name' in {service_name} service should not be empty"
                )

                # Check endpoint URL is valid
                endpoint_url = service.get("endpoint_url")
                if endpoint_url:
                    self.assertIsInstance(
                        endpoint_url, str, f"The 'endpoint_url' in {service_name} service should be a string"
                    )
                    self.assertTrue(
                        endpoint_url.startswith(("http://", "https://")),
                        f"The 'endpoint_url' in {service_name} service should start with http:// or https://",
                    )

    def test_all_required_extractors_exist(self):
        """Test that all extractor modules referenced in config actually exist."""
        if not self.config:
            self.skipTest("Config file not found")

        # Collect all unique extractor modules used
        extractor_modules = set()

        for service in self.config:
            for field in service.get("fields", []):
                func_path = field.get("func", "")
                if "extractors" in func_path:
                    module_path = func_path.rsplit(".", 1)[0]
                    extractor_modules.add(module_path)

        # Test that each module can be imported
        for module_path in extractor_modules:
            with self.subTest(module=module_path):
                try:
                    __import__(module_path)
                except ImportError as e:
                    self.fail(f"Could not import extractor module {module_path}: {e}")

    def test_all_required_filters_exist(self):
        """Test that all filter modules referenced in config actually exist."""
        if not self.config:
            self.skipTest("Config file not found")

        # Collect all unique filter modules used
        filter_modules = set()

        for service in self.config:
            for filter_config in service.get("filters", []):
                func_path = filter_config.get("func", "")
                if "filters" in func_path:
                    module_path = func_path.rsplit(".", 1)[0]
                    filter_modules.add(module_path)

        # Test that each module can be imported
        for module_path in filter_modules:
            with self.subTest(module=module_path):
                try:
                    __import__(module_path)
                except ImportError as e:
                    self.fail(f"Could not import filter module {module_path}: {e}")

    def test_field_args_are_valid_types(self):
        """Test that field arguments are of valid types (string or list)."""
        if not self.config:
            self.skipTest("Config file not found")

        for service_idx, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{service_idx}")
            fields = service.get("fields", [])

            for field in fields:
                args = field.get("args")
                if args is not None:
                    with self.subTest(service=service_name, field=field.get("name")):
                        self.assertIsInstance(
                            args,
                            (str, list),
                            f"The arguments in the '{field.get('name')}' field in "
                            f"{service_name} service should be string or list, got {type(args)}",
                        )

    def test_filter_args_are_valid_types(self):
        """Test that filter arguments are of valid types (string or list)."""
        if not self.config:
            self.skipTest("Config file not found")

        for service_idx, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{service_idx}")
            filters = service.get("filters", [])

            for filter_idx, filter_config in enumerate(filters):
                args = filter_config.get("args")
                if args is not None:
                    with self.subTest(service=service_name, filter_idx=filter_idx):
                        self.assertIsInstance(
                            args,
                            (str, list),
                            f"The arguments in the '{filter_config.get('name')}' filter in "
                            f"{service_name} service should be string or list, got {type(args)}",
                        )

    def test_no_duplicate_service_names(self):
        """Test that there are no duplicate service names in the configuration."""
        if not self.config:
            self.skipTest("Config file not found")

        service_names = [service.get("service_name") for service in self.config]
        unique_service_names = set(service_names)

        self.assertEqual(len(service_names), len(unique_service_names), "Service names should be unique")

    def test_no_duplicate_field_names_per_service(self):
        """Test that there are no duplicate field names within each service."""
        if not self.config:
            self.skipTest("Config file not found")

        for service_idx, service in enumerate(self.config):
            service_name = service.get("service_name", f"service_{service_idx}")
            fields = service.get("fields", [])

            with self.subTest(service=service_name):
                field_names = [field.get("name") for field in fields if field.get("name")]
                unique_field_names = set(field_names)

                self.assertEqual(
                    len(field_names),
                    len(unique_field_names),
                    f"Field names should be unique within the {service_name} service",
                )
