"""
Tests for the CertificateEngine.
"""

import base64
import hashlib
from unittest.mock import Mock, patch

from ddt import data, ddt
from django.test import TestCase
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.coursecertificate.engine import CertificateEngine
from nau_openedx_extensions.coursecertificate.tests.fixtures import Certificate, User

ENGINE_MODULE_PATH = "nau_openedx_extensions.coursecertificate.engine"


# pylint: disable=protected-access
@ddt
class TestCertificateEngine(TestCase):
    """
    Test the CertificateEngine class.
    """

    def setUp(self):
        """Set up test data and configuration."""
        self.engine = CertificateEngine()

        self.user1 = User()
        self.user2 = User()
        self.users = [self.user1, self.user2]
        self.certificate1 = Certificate(self.user1)
        self.certificate2 = Certificate(self.user2)
        self.certificates = [self.certificate1, self.certificate2]

    @data("MD5", "md5", "Md5", "mD5", " MD5", "md5 ")
    def test_apply_transformations_md5(self, trans: str):
        """Test MD5 transformation."""
        test_value = "test@example.com"
        result = self.engine.apply_transformations(test_value, trans)

        expected = hashlib.md5(test_value.encode()).hexdigest()
        self.assertEqual(result, expected)

    @data("BASE64", "base64", "Base64", "bASE64", " BASE64", "base64 ")
    def test_apply_transformations_base64(self, trans: str):
        """Test base64 transformation."""
        test_value = "test-course"
        result = self.engine.apply_transformations(test_value, trans)

        expected = base64.b64encode(test_value.encode()).decode()
        self.assertEqual(result, expected)

    @data("sha256", "sha512", "sha1", "", "    ")
    def test_apply_transformations_unsupported_raises_value_error(self, trans):
        """Test that unsupported transformations raise ValueError."""
        test_value = "test_value"

        with self.assertRaises(ValueError):
            self.engine.apply_transformations(test_value, trans)

    def test_apply_transformations_all_supported(self):
        """Test all supported transformations."""
        test_value = "test@example.com"

        md5_result = self.engine.apply_transformations(test_value, "md5")
        expected_md5 = hashlib.md5(test_value.encode()).hexdigest()
        self.assertEqual(md5_result, expected_md5)

        base64_result = self.engine.apply_transformations(test_value, "base64")
        expected_base64 = base64.b64encode(test_value.encode()).decode()
        self.assertEqual(base64_result, expected_base64)

    def test_transformations_are_consistent(self):
        """Test that transformations produce consistent results."""
        test_value = "consistent_test"

        # Multiple calls should produce same result
        result1 = self.engine.apply_transformations(test_value, "md5")
        result2 = self.engine.apply_transformations(test_value, "md5")
        self.assertEqual(result1, result2)

        result3 = self.engine.apply_transformations(test_value, "base64")
        result4 = self.engine.apply_transformations(test_value, "base64")
        self.assertEqual(result3, result4)

    def test_transform_md5_private_method(self):
        """Test private MD5 transformation method."""
        test_value = "test@example.com"
        result = self.engine._transform_md5(test_value)
        expected = hashlib.md5(test_value.encode()).hexdigest()
        self.assertEqual(result, expected)

    def test_transform_base64_private_method(self):
        """Test private base64 transformation method."""
        test_value = "test-course"
        result = self.engine._transform_base64(test_value)
        expected = base64.b64encode(test_value.encode()).decode()
        self.assertEqual(result, expected)

    def test_extract_field_value_success(self):
        """Test successful field value extraction."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
        }
        certificate = Mock()
        certificate.user.email = "test@example.com"
        result = self.engine.extract_field_value(certificate, field_config)

        self.assertEqual(result, "test@example.com")

    def test_extract_field_value_with_args(self):
        """Test field value extraction with arguments."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student_nau_user_extended_model_field",
            "args": ["nif"],
        }

        certificate = Mock()
        certificate.user.nauuserextendedmodel.nif = "123456789"
        result = self.engine.extract_field_value(certificate, field_config)

        self.assertEqual(result, "123456789")

    def test_extract_field_value_with_transformation_md5(self):
        """Test field value extraction with transformation."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
            "trans": "md5",
        }
        certificate = Mock()
        certificate.user.email = "test@example.com"
        result = self.engine.extract_field_value(certificate, field_config)
        expected = hashlib.md5("test@example.com".encode()).hexdigest()
        self.assertEqual(result, expected)

    def test_extract_field_value_with_transformation_base64(self):
        """Test field value extraction with transformation."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
            "trans": "base64",
        }
        certificate = Mock()
        certificate.user.email = "test@example.com"
        result = self.engine.extract_field_value(certificate, field_config)
        expected = base64.b64encode("test@example.com".encode()).decode()
        self.assertEqual(result, expected)

    def test_extract_field_value_import_error(self):
        """Test field value extraction with import error."""
        field_config = {
            "name": "test_field",
            "func": "nonexistent.module.function",
        }
        certificate = Mock()
        result = self.engine.extract_field_value(certificate, field_config)

        self.assertIsNone(result)

    def test_extract_field_value_attribute_error(self):
        """Test field value extraction with attribute error."""
        field_config = {
            "name": "test_field",
            "func": "nau_openedx_extensions.coursecertificate.extractors.student.nonexistent_function",
        }
        certificate = Mock()
        result = self.engine.extract_field_value(certificate, field_config)

        self.assertIsNone(result)

    @patch("nau_openedx_extensions.coursecertificate.filters.certificate_by_org")
    def test_apply_filters_success(self, mock_certificate_by_org: Mock):
        """Test applying filters successfully."""
        self.certificates[0].course_id = CourseKey.from_string("course-v1:NAU+Demo1+Course")
        self.certificates[1].course_id = CourseKey.from_string("course-v1:OpenedX+Demo2+Course")
        mock_certificate_by_org.return_value = [self.certificates[0]]

        service_config = {
            "filters": [
                {
                    "func": "nau_openedx_extensions.coursecertificate.filters.certificate_by_org",
                    "args": "NAU",
                }
            ]
        }

        result = self.engine.apply_filters(self.certificates, service_config)

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

        result = self.engine.apply_filters(self.certificates, service_config)

        # Should return original queryset when filter fails
        self.assertEqual(result, self.certificates)

    def test_convert_certificates_to_service_format(self):
        """Test converting certificates to service format."""
        service_config = {
            "fields": [
                {
                    "name": "certificate_date",
                    "func": "nau_openedx_extensions.coursecertificate.extractors.certificate_date",
                },
                {
                    "name": "student_email",
                    "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                },
            ]
        }
        result = self.engine.convert_certificates_to_service_format(self.certificates, service_config)

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
                    "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                },
                {
                    "name": "invalid_field",
                    "func": "nonexistent.module.function",  # This will fail
                },
            ]
        }

        result = self.engine.convert_certificates_to_service_format(self.certificates, service_config)

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

        result = self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

        self.assertTrue(result)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://api.test.com/certificates")
        self.assertEqual(call_args[1]["json"], certificates_data)
        self.assertIn("Authorization", call_args[1]["headers"])
        # Verify default timeout is used
        self.assertEqual(call_args[1]["timeout"], 60)

    @patch("requests.post")
    def test_send_certificates_to_service_with_custom_timeout(self, mock_post: Mock):
        """Test sending certificates with custom timeout."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.text = "Success"
        mock_post.return_value = mock_response

        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "bearer",
            "endpoint_timeout": 120,  # Custom timeout
        }

        certificates_data = [{"certificate_id": "123", "email": "test@example.com"}]

        result = self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

        self.assertTrue(result)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://api.test.com/certificates")
        self.assertEqual(call_args[1]["json"], certificates_data)
        self.assertIn("Authorization", call_args[1]["headers"])
        # Verify custom timeout is used
        self.assertEqual(call_args[1]["timeout"], 120)

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

        result = self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

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

        # Note: The engine re-raises the exception, so we need to catch it
        with self.assertRaises(Exception):
            self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

    @patch("requests.post")
    def test_send_certificates_to_service_dry_run(self, mock_post: Mock):
        """Test sending certificates in dry run mode."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "bearer",
        }

        certificates_data = [{"certificate_id": "123", "email": "test@example.com"}]

        result = self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=True)

        self.assertTrue(result)
        mock_post.assert_not_called()

    @patch("requests.post")
    def test_send_certificates_to_service_dry_run_parameter(self, mock_post: Mock):
        """Test sending certificates in dry run mode using parameter."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "bearer",
        }

        certificates_data = [{"certificate_id": "123", "email": "test@example.com"}]

        result = self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=True)

        self.assertTrue(result)
        mock_post.assert_not_called()

    @patch("requests.post")
    def test_send_certificates_to_service_not_dry_run(self, mock_post: Mock):
        """Test sending certificates when dry_run=False."""
        mock_response = Mock()
        mock_response.ok = True
        mock_post.return_value = mock_response

        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "bearer",
        }

        certificates_data = [{"certificate_id": "123"}]

        result = self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

        self.assertTrue(result)
        mock_post.assert_called_once()

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

            self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

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

            self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

            call_args = mock_post.call_args
            headers = call_args[1]["headers"]
            self.assertIn("X-API-Key", headers)
            self.assertEqual(headers["X-API-Key"], "api_key_123")

    @patch(f"{ENGINE_MODULE_PATH}.GeneratedCertificate")
    @patch(f"{ENGINE_MODULE_PATH}.use_read_replica_if_available")
    def test_get_certificates_queryset(self, mock_use_read_replica: Mock, mock_certificate_model: Mock):
        """Test getting certificates queryset."""
        mock_queryset = Mock()
        mock_use_read_replica.return_value = mock_queryset

        result = self.engine.get_certificates_queryset(7)

        self.assertEqual(result, mock_queryset)
        mock_use_read_replica.assert_called_once()
        mock_certificate_model.objects.filter.assert_called_once()

    def test_send_certificates_invalid_auth_type(self):
        """Test sending certificates with invalid auth_type raises ValueError."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "invalid_auth",
        }

        certificates_data = [{"certificate_id": "123"}]

        with self.assertRaises(ValueError) as context:
            self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

        self.assertIn("Invalid auth_type 'invalid_auth'", str(context.exception))
        self.assertIn("Valid options: bearer, basic, api_key", str(context.exception))

    def test_send_certificates_valid_auth_types(self):
        """Test that all valid auth_types are accepted."""
        valid_auth_types = ["bearer", "basic", "api_key"]

        for auth_type in valid_auth_types:
            with self.subTest(auth_type=auth_type):
                service_config = {
                    "service_name": "test_service",
                    "endpoint_url": "https://api.test.com/certificates",
                    "auth_token": "test_token",
                    "auth_type": auth_type,
                }

                certificates_data = [{"certificate_id": "123"}]

                with patch("requests.post") as mock_post:
                    mock_response = Mock()
                    mock_response.ok = True
                    mock_post.return_value = mock_response

                    result = self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)
                    self.assertTrue(result)

    def test_send_certificates_case_sensitive_auth_type(self):
        """Test that auth_type is case sensitive."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "Bearer",
        }

        certificates_data = [{"certificate_id": "123"}]

        with self.assertRaises(ValueError) as context:
            self.engine.send_certificates_to_service(service_config, certificates_data, dry_run=False)

        self.assertIn("Invalid auth_type 'Bearer'", str(context.exception))

    def test_valid_auth_types_constant(self):
        """Test that VALID_AUTH_TYPES constant is properly defined."""
        self.assertIsInstance(self.engine.VALID_AUTH_TYPES, list)
        self.assertIn("bearer", self.engine.VALID_AUTH_TYPES)
        self.assertIn("basic", self.engine.VALID_AUTH_TYPES)
        self.assertIn("api_key", self.engine.VALID_AUTH_TYPES)
        self.assertEqual(len(self.engine.VALID_AUTH_TYPES), 3)

    def test_auth_type_validation_uses_class_constant(self):
        """Test that auth_type validation uses the class constant."""
        # Verify that the engine raises an error for an invalid auth_type
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "auth_type": "invalid",
        }

        with self.assertRaises(ValueError) as context:
            self.engine.send_certificates_to_service(service_config, [], dry_run=False)

        error_message = str(context.exception)
        for valid_type in self.engine.VALID_AUTH_TYPES:
            self.assertIn(valid_type, error_message)

    def test_validate_service_config_valid(self):
        """Test service config validation with valid config."""
        service_config = {
            "service_name": "test_service",
            "auth_type": "bearer",
        }

        # Should not raise any exception
        self.engine._validate_service_config(service_config)

    def test_validate_service_config_invalid_auth_type(self):
        """Test service config validation with invalid auth type."""
        service_config = {
            "service_name": "test_service",
            "auth_type": "invalid_type",
        }

        with self.assertRaises(ValueError) as context:
            self.engine._validate_service_config(service_config)

        self.assertIn("Invalid auth_type 'invalid_type'", str(context.exception))

    def test_prepare_auth_headers_bearer(self):
        """Test preparing auth headers for bearer authentication."""
        service_config = {
            "auth_token": "test_token",
            "auth_type": "bearer",
        }

        headers = self.engine._prepare_auth_headers(service_config)

        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer test_token")

    def test_prepare_auth_headers_basic(self):
        """Test preparing auth headers for basic authentication."""
        service_config = {
            "auth_token": "user:pass",
            "auth_type": "basic",
        }

        headers = self.engine._prepare_auth_headers(service_config)

        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("Basic "))

    def test_prepare_auth_headers_api_key(self):
        """Test preparing auth headers for API key authentication."""
        service_config = {
            "auth_token": "api_key_123",
            "auth_type": "api_key",
            "auth_header": "X-API-Key",
        }

        headers = self.engine._prepare_auth_headers(service_config)

        self.assertIn("X-API-Key", headers)
        self.assertEqual(headers["X-API-Key"], "api_key_123")

    def test_prepare_auth_headers_no_token(self):
        """Test preparing auth headers without token."""
        service_config = {}

        headers = self.engine._prepare_auth_headers(service_config)

        self.assertNotIn("Authorization", headers)
        self.assertIn("Accept", headers)
        self.assertIn("Content-Type", headers)

    def test_get_processing_parameters_defaults(self):
        """Test getting processing parameters with defaults."""
        service_config = {}
        options = {}

        params = self.engine._get_processing_parameters(service_config, options)

        self.assertEqual(params["days"], 7)
        self.assertEqual(params["page_size"], 1000)
        self.assertEqual(params["dry_run"], False)

    def test_get_processing_parameters_service_config_override(self):
        """Test getting processing parameters with service config overrides."""
        service_config = {
            "days": 14,
            "page_size": 500,
        }
        options = {}

        params = self.engine._get_processing_parameters(service_config, options)

        self.assertEqual(params["days"], 14)
        self.assertEqual(params["page_size"], 500)
        self.assertEqual(params["dry_run"], False)

    def test_get_processing_parameters_options_override(self):
        """Test getting processing parameters with options overrides."""
        service_config = {
            "days": 14,
            "page_size": 500,
        }
        options = {
            "days": 21,
            "page_size": 100,
            "dry_run": True,
        }

        params = self.engine._get_processing_parameters(service_config, options)

        self.assertEqual(params["days"], 21)
        self.assertEqual(params["page_size"], 100)
        self.assertEqual(params["dry_run"], True)

    def test_process_certificates_page_empty(self):
        """Test processing empty certificates page."""
        service_config = {}
        result = self.engine._process_certificates_page([], service_config, dry_run=False)

        self.assertTrue(result)

    def test_process_certificates_page_with_data(self):
        """Test processing certificates page with data."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "fields": [
                {
                    "name": "student_email",
                    "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                }
            ],
        }

        with patch.object(self.engine, "send_certificates_to_service", return_value=True) as mock_send:
            result = self.engine._process_certificates_page(self.certificates, service_config, dry_run=False)

            self.assertTrue(result)
            mock_send.assert_called_once()

    def test_process_certificates_pages(self):
        """Test processing certificates in pages."""
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
            "fields": [
                {
                    "name": "student_email",
                    "func": "nau_openedx_extensions.coursecertificate.extractors.student_email",
                }
            ],
        }

        params = {
            "page_size": 1,
            "dry_run": False,
        }

        with patch.object(self.engine, "_process_certificates_page", return_value=True) as mock_process_page:
            self.engine._process_certificates_pages(self.certificates, service_config, params)

            # Should be called twice (one for each certificate)
            self.assertEqual(mock_process_page.call_count, 2)

    @patch.object(CertificateEngine, "get_certificates_queryset")
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

        with patch.object(self.engine, "_process_certificates_pages") as mock_process_pages:
            self.engine.process_service(service_config, options)

            mock_get_queryset.assert_called_once_with(7)
            mock_process_pages.assert_called_once()

    @patch.object(CertificateEngine, "get_certificates_queryset")
    def test_process_service_with_defaults(self, mock_get_queryset: Mock):
        """Test processing service with default values."""
        mock_get_queryset.return_value = []
        service_config = {
            "service_name": "test_service",
            "endpoint_url": "https://api.test.com/certificates",
        }
        options = {}

        with patch.object(self.engine, "_process_certificates_pages") as mock_process_pages:
            self.engine.process_service(service_config, options)

            mock_get_queryset.assert_called_once_with(7)
            mock_process_pages.assert_called_once()

    def test_log_dry_run_info(self):
        """Test dry run info logging."""
        service_config = {
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "bearer",
        }

        certificates_data = [{"certificate_id": "123"}]

        # Capture log output
        log_output = []

        def mock_log(msg):
            log_output.append(msg)

        self.engine.log = mock_log

        self.engine._log_dry_run_info(service_config, certificates_data)

        log_messages = " ".join(log_output)
        self.assertIn("Would send to https://api.test.com/certificates", log_messages)
        self.assertIn("bearer authentication", log_messages)
        self.assertIn("Auth token: Configured", log_messages)
        self.assertIn("Request timeout: 60 seconds", log_messages)
        self.assertIn("Payload:", log_messages)

    def test_log_dry_run_info_with_custom_timeout(self):
        """Test dry run info logging with custom timeout."""
        service_config = {
            "endpoint_url": "https://api.test.com/certificates",
            "auth_token": "test_token",
            "auth_type": "bearer",
            "endpoint_timeout": 120,  # Custom timeout
        }

        certificates_data = [{"certificate_id": "123"}]

        # Capture log output
        log_output = []

        def mock_log(msg):
            log_output.append(msg)

        self.engine.log = mock_log

        self.engine._log_dry_run_info(service_config, certificates_data)

        log_messages = " ".join(log_output)
        self.assertIn("Would send to https://api.test.com/certificates", log_messages)
        self.assertIn("bearer authentication", log_messages)
        self.assertIn("Auth token: Configured", log_messages)
        self.assertIn("Request timeout: 120 seconds", log_messages)
        self.assertIn("Payload:", log_messages)

    def test_send_http_request_success(self):
        """Test successful HTTP request."""
        api_url = "https://api.test.com/certificates"
        headers = {"Authorization": "Bearer token"}
        certificates_data = [{"certificate_id": "123"}]
        timeout = 60

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.ok = True
            mock_post.return_value = mock_response

            result = self.engine._send_http_request(api_url, headers, certificates_data, timeout)

            self.assertTrue(result)
            mock_post.assert_called_once_with(
                api_url,
                json=certificates_data,
                headers=headers,
                timeout=timeout,
            )

    def test_send_http_request_with_custom_timeout(self):
        """Test HTTP request with custom timeout."""
        api_url = "https://api.test.com/certificates"
        headers = {"Authorization": "Bearer token"}
        certificates_data = [{"certificate_id": "123"}]
        timeout = 120  # Custom timeout

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.ok = True
            mock_post.return_value = mock_response

            result = self.engine._send_http_request(api_url, headers, certificates_data, timeout)

            self.assertTrue(result)
            mock_post.assert_called_once_with(
                api_url,
                json=certificates_data,
                headers=headers,
                timeout=timeout,
            )

    def test_send_http_request_failure(self):
        """Test failed HTTP request."""
        api_url = "https://api.test.com/certificates"
        headers = {"Authorization": "Bearer token"}
        certificates_data = [{"certificate_id": "123"}]
        timeout = 60

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.ok = False
            mock_response.text = "Error message"
            mock_post.return_value = mock_response

            result = self.engine._send_http_request(api_url, headers, certificates_data, timeout)

            self.assertFalse(result)

    def test_send_http_request_exception(self):
        """Test HTTP request with exception."""
        api_url = "https://api.test.com/certificates"
        headers = {"Authorization": "Bearer token"}
        certificates_data = [{"certificate_id": "123"}]
        timeout = 60

        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Connection error")

            with self.assertRaises(Exception) as context:
                self.engine._send_http_request(api_url, headers, certificates_data, timeout)

            self.assertEqual(str(context.exception), "Connection error")

    def test_engine_initialization_with_logger(self):
        """Test engine initialization with custom logger."""

        def custom_logger(_):
            pass

        engine = CertificateEngine(logger=custom_logger)

        self.assertEqual(engine.log, custom_logger)

    def test_engine_initialization_without_logger(self):
        """Test engine initialization without logger (uses print)."""
        engine = CertificateEngine()

        self.assertEqual(engine.log, print)
