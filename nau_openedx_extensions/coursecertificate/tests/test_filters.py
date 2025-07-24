"""
Unit tests for certificate filters module.
"""

from unittest.mock import Mock

from ddt import data, ddt, unpack
from django.db.models.query import QuerySet
from django.test import TestCase

from nau_openedx_extensions.coursecertificate.filters import certificate_by_course_id_regex, certificate_by_org


@ddt
class TestCertificateFilters(TestCase):
    """Test cases for certificate filtering functions."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_certificates = Mock(spec=QuerySet)
        self.mock_filtered_result = Mock(spec=QuerySet)

    @data(
        r"^course-v1:MIT\+.*",
        r"",
        r"^course-v1:(MIT|Harvard)\+.*CS.*",
        r"^course-v1:Test\.Org\+.*\$",
    )
    def test_certificate_by_course_id_regex_valid_regex(self, course_id_regex: str):
        """Test certificate_by_course_id_regex with valid regex pattern."""
        self.mock_certificates.filter.return_value = self.mock_filtered_result

        result = certificate_by_course_id_regex(self.mock_certificates, course_id_regex)

        self.mock_certificates.filter.assert_called_once_with(course_id__regex=course_id_regex)
        self.assertEqual(result, self.mock_filtered_result)

    @data(
        ("MIT", r"^course-v1:MIT\+"),
        ("mit", r"^course-v1:mit\+"),
        ("Harvard", r"^course-v1:Harvard\+"),
        ("Stanford.University", r"^course-v1:Stanford.University\+"),
        ("123Org", r"^course-v1:123Org\+"),
        ("Test.Org", r"^course-v1:Test.Org\+"),
        ("Org-Name", r"^course-v1:Org-Name\+"),
    )
    @unpack
    def test_certificate_by_org_valid_org(self, org: str, expected_regex: str):
        """Test certificate_by_org with valid organization name."""
        self.mock_certificates.filter.return_value = self.mock_filtered_result

        result = certificate_by_org(self.mock_certificates, org)

        self.mock_certificates.filter.assert_called_once_with(course_id__regex=expected_regex)
        self.assertEqual(result, self.mock_filtered_result)

    def test_both_functions_return_queryset(self):
        """Test that both functions return QuerySet instances."""
        course_id_regex = r"^course-v1:MIT\+.*"
        org = "MIT"

        mock_result = Mock(spec=QuerySet)
        self.mock_certificates.filter.return_value = mock_result

        result1 = certificate_by_course_id_regex(self.mock_certificates, course_id_regex)
        result2 = certificate_by_org(self.mock_certificates, org)
        self.assertIsInstance(result1, type(mock_result))
        self.assertIsInstance(result2, type(mock_result))

    def test_functions_preserve_original_queryset(self):
        """Test that functions don't modify the original QuerySet."""
        original_certificates = Mock(spec=QuerySet)
        course_id_regex = r"^course-v1:MIT\+.*"
        org = "MIT"

        certificate_by_course_id_regex(original_certificates, course_id_regex)
        certificate_by_org(original_certificates, org)

        self.assertEqual(original_certificates.filter.call_count, 2)
