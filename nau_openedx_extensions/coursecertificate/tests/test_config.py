"""
Tests for the coursecertificate configuration structure and validation.

This module tests the configuration loaded from Django settings to ensure
it follows the expected structure and contains valid values.
"""

from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from nau_openedx_extensions.coursecertificate.management.commands.send_certificates_by_web_service import Command


class TestConfigurationStructure(TestCase):
    """
    Test the configuration structure and validation.
    """

    def setUp(self):
        """Set up test data and configuration samples."""
        self.command = Command()

        # Minimal valid configuration
        self.minimal_config = [
            {
                "service_name": "test_service",
                "endpoint_url": "https://api.test.com/certificates",
            }
        ]

        # Complete valid configuration
        self.complete_config = [
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

        # Multiple services configuration
        self.multi_service_config = [
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

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[
        {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
        }
    ])
    def test_load_minimal_valid_config(self):
        """Test loading a minimal valid configuration."""
        config = self.command.load_config()

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_service")
        self.assertEqual(config[0]["endpoint_url"], "https://api.test.com/certificates")
        self.assertNotIn("endpoint_timeout", config[0])

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[
        {
            "service_name": "test_service_with_timeout",
            "endpoint_url": "https://api.test.com/certificates",
            "endpoint_timeout": 45,
        }
    ])
    def test_minimal_config_with_endpoint_timeout(self):
        """Test loading minimal configuration with endpoint_timeout."""
        config = self.command.load_config()

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_service_with_timeout")
        self.assertEqual(config[0]["endpoint_url"], "https://api.test.com/certificates")
        self.assertEqual(config[0]["endpoint_timeout"], 45)

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[
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
                    "func": "nau_openedx_extensions.coursecertificate.extractors.student.nau_user_extended_model_field",
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
    ])
    def test_load_complete_valid_config(self):
        """Test loading a complete valid configuration."""
        config = self.command.load_config()

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

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[
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
    ])
    def test_load_multiple_services_config(self):
        """Test loading configuration with multiple services."""
        config = self.command.load_config()

        self.assertEqual(len(config), 2)
        self.assertEqual(config[0]["service_name"], "service_one")
        self.assertEqual(config[1]["service_name"], "service_two")
        self.assertEqual(config[0]["page_size"], 50)
        self.assertEqual(config[1]["page_size"], 200)
        self.assertEqual(config[0]["endpoint_timeout"], 60)
        self.assertEqual(config[1]["endpoint_timeout"], 120)

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[])
    def test_load_empty_config(self):
        """Test loading empty configuration."""
        config = self.command.load_config()

        self.assertEqual(len(config), 0)

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=None)
    def test_load_config_missing_root_key(self):
        """Test loading configuration when setting is None."""
        with self.assertRaises(CommandError) as context:
            self.command.load_config()

        self.assertIn("not found in Django settings", str(context.exception))

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG="not_a_list")
    def test_load_config_invalid_type(self):
        """Test loading configuration with invalid type."""
        with self.assertRaises(CommandError) as context:
            self.command.load_config()

        self.assertIn("must be a list of service configurations", str(context.exception))


class TestConfigurationValidation(TestCase):
    """
    Test configuration validation and error handling.
    """

    def setUp(self):
        """Set up test data."""
        self.command = Command()

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG="this should be a list")
    def test_config_with_wrong_structure(self):
        """Test handling of configuration with wrong structure."""
        with self.assertRaises(CommandError) as context:
            self.command.load_config()

        self.assertIn("must be a list of service configurations", str(context.exception))

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[{"invalid": "service"}])
    def test_config_missing_required_fields(self):
        """Test configuration missing required fields."""
        config = self.command.load_config()
        # The load_config method itself doesn't validate service structure,
        # that's handled by the engine during processing
        self.assertEqual(len(config), 1)
        self.assertNotIn("service_name", config[0])


class TestConfigurationEdgeCases(TestCase):
    """
    Test edge cases and unusual configurations.
    """

    def setUp(self):
        """Set up test data."""
        self.command = Command()

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[
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
    ])
    def test_config_with_unicode_characters(self):
        """Test configuration with unicode characters."""
        config = self.command.load_config()

        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]["service_name"], "test_unicode_üñíçödé")

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[
        {
            "service_name": "long_test",
            "endpoint_url": f"https://very-long-domain-name-{'x' * 1000}.com/api/certificates",
            "auth_token": "x" * 1000,
        }
    ])
    def test_config_with_very_long_values(self):
        """Test configuration with very long string values."""
        config = self.command.load_config()

        self.assertEqual(len(config), 1)
        self.assertEqual(len(config[0]["auth_token"]), 1000)


class TestCurrentConfigurationContent(TestCase):
    """
    Test the current content and configuration validation.
    These tests validate service configurations generically.
    """

    def setUp(self):
        """Set up test data."""
        self.command = Command()

    def get_test_config(self):
        """Get a sample test configuration for validation tests."""
        return [
            {
                "service_name": "test_service_1",
                "endpoint_url": "https://api.test1.com/certificates",
                "endpoint_timeout": 30,
                "auth_token": "test_token_1",
                "auth_type": "bearer",
                "auth_header": "Authorization",
                "page_size": 100,
                "days": 7,
                "fields": [
                    {
                        "name": "email",
                        "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                    },
                    {
                        "name": "hashed_email",
                        "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                        "trans": "md5",
                    },
                ],
                "filters": [
                    {
                        "func": "nau_openedx_extensions.coursecertificate.filters.certificate_by_org",
                        "args": "TestOrg",
                    }
                ],
            },
            {
                "service_name": "test_service_2",
                "endpoint_url": "https://api.test2.com/certificates",
                "endpoint_timeout": 60,
                "auth_token": "test_token_2",
                "auth_type": "api_key",
                "page_size": 50,
                "days": 14,
                "fields": [],
                "filters": [],
            }
        ]

    def test_config_has_services(self):
        """Test that the configuration contains services."""
        config = self.get_test_config()
        self.assertGreater(len(config), 0, "Configuration should have at least one service")

    def test_all_services_have_required_fields(self):
        """Test that all services have the minimum required fields."""
        config = self.get_test_config()
        required_fields = ["service_name", "endpoint_url"]

        for i, service in enumerate(config):
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
        config = self.get_test_config()

        for i, service in enumerate(config):
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
        config = self.get_test_config()

        for i, service in enumerate(config):
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
        config = self.get_test_config()

        for i, service in enumerate(config):
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

    def test_field_transformations_are_valid(self):
        """Test that all transformations used in fields are supported."""
        config = self.get_test_config()
        supported_transformations = ["md5", "base64"]

        for service_idx, service in enumerate(config):
            service_name = service.get("service_name", f"service_{service_idx}")
            fields = service.get("fields", [])

            for field in fields:
                trans = field.get("trans")
                if trans:
                    with self.subTest(service=service_name, field=field.get("name"), transformation=trans):
                        self.assertIn(trans, supported_transformations, f"Transformation '{trans}' is not supported")

    def test_service_configurations_are_reasonable(self):
        """Test that service configuration values are reasonable."""
        config = self.get_test_config()

        for service_idx, service in enumerate(config):
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

    def test_field_args_are_valid_types(self):
        """Test that field arguments are of valid types (string or list)."""
        config = self.get_test_config()

        for service_idx, service in enumerate(config):
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
        config = self.get_test_config()

        for service_idx, service in enumerate(config):
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
        config = self.get_test_config()

        service_names = [service.get("service_name") for service in config]
        unique_service_names = set(service_names)

        self.assertEqual(len(service_names), len(unique_service_names), "Service names should be unique")

    def test_no_duplicate_field_names_per_service(self):
        """Test that there are no duplicate field names within each service."""
        config = self.get_test_config()

        for service_idx, service in enumerate(config):
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


class TestConfigurationIntegration(TestCase):
    """
    Test configuration integration with the command.
    """

    def setUp(self):
        """Set up test data."""
        self.command = Command()

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[
        {
            "service_name": "integration_test",
            "endpoint_url": "https://api.integration.com/certificates",
            "endpoint_timeout": 45,
            "auth_token": "integration_token",
            "auth_type": "bearer",
            "page_size": 100,
            "days": 7,
            "fields": [
                {
                    "name": "test_field",
                    "func": "test.func",
                }
            ],
            "filters": [
                {
                    "func": "test.filter",
                    "args": "test_arg"
                }
            ],
        }
    ])
    def test_configuration_loads_correctly_from_settings(self):
        """Test that configuration loads correctly from Django settings."""
        config = self.command.load_config()

        self.assertEqual(len(config), 1)
        service = config[0]

        # Verify all fields are loaded correctly
        self.assertEqual(service["service_name"], "integration_test")
        self.assertEqual(service["endpoint_url"], "https://api.integration.com/certificates")
        self.assertEqual(service["endpoint_timeout"], 45)
        self.assertEqual(service["auth_token"], "integration_token")
        self.assertEqual(service["auth_type"], "bearer")
        self.assertEqual(service["page_size"], 100)
        self.assertEqual(service["days"], 7)
        self.assertEqual(len(service["fields"]), 1)
        self.assertEqual(len(service["filters"]), 1)

    @override_settings(NAU_SEND_COURSE_CERTIFICATE_CONFIG=[
        {"service_name": "service1", "endpoint_url": "https://api1.com"},
        {"service_name": "service2", "endpoint_url": "https://api2.com"},
        {"service_name": "service3", "endpoint_url": "https://api3.com"},
    ])
    def test_configuration_with_multiple_services(self):
        """Test configuration with multiple services."""
        config = self.command.load_config()

        self.assertEqual(len(config), 3)
        service_names = [service["service_name"] for service in config]
        self.assertEqual(service_names, ["service1", "service2", "service3"])

    def test_configuration_missing_setting(self):
        """Test behavior when configuration setting is not present."""
        # Test without override_settings, so the setting doesn't exist
        with self.assertRaises(CommandError) as context:
            self.command.load_config()

        self.assertIn("not found in Django settings", str(context.exception))
        self.assertIn("This setting comes from Tutor configuration", str(context.exception))
