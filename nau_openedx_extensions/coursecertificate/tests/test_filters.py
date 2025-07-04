"""
Tests for the filters modules used in coursecertificate.
"""

import re
from unittest.mock import Mock

from django.db.models.query import QuerySet
from django.test import TestCase

from nau_openedx_extensions.coursecertificate.filters import certificate_by_course_id_regex, certificate_by_org
from nau_openedx_extensions.coursecertificate.tests.fixtures import Certificate, User


class TestCertificateByOrgFilter(TestCase):
    """
    Test the certificate_by_org filter function.
    """

    def setUp(self):
        """Set up test data."""
        self.user1 = User()
        self.user2 = User()
        self.user3 = User()

        # Create certificates with different organizations
        self.cert1 = Certificate(self.user1)
        self.cert1.course_id = self.cert1.course_id.replace(org="edX")

        self.cert2 = Certificate(self.user2)
        self.cert2.course_id = self.cert2.course_id.replace(org="MITx")

        self.cert3 = Certificate(self.user3)
        self.cert3.course_id = self.cert3.course_id.replace(org="edX")

        # Create a mock QuerySet with the certificates
        self.certificates = Mock(spec=QuerySet)
        self.certificates.__iter__ = Mock(return_value=iter([self.cert1, self.cert2, self.cert3]))

    def test_filter_by_existing_org(self):
        """
        Test filtering certificates by an existing organization.

        Expected result:
        - Returns only certificates from the specified organization
        """
        result = certificate_by_org(self.certificates, "edX")

        self.assertEqual(len(result), 2)
        self.assertIn(self.cert1, result)
        self.assertIn(self.cert3, result)
        self.assertNotIn(self.cert2, result)

    def test_filter_by_nonexistent_org(self):
        """
        Test filtering certificates by a non-existent organization.

        Expected result:
        - Returns an empty list when no certificates match the organization
        """
        result = certificate_by_org(self.certificates, "NonExistentOrg")

        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, list)

    def test_filter_by_case_sensitive_org(self):
        """
        Test that organization filtering is case sensitive.

        Expected result:
        - Returns empty list when case doesn't match exactly
        """
        result = certificate_by_org(self.certificates, "edx")

        self.assertEqual(len(result), 0)

    def test_filter_empty_certificates_list(self):
        """
        Test filtering an empty QuerySet of certificates.

        Expected result:
        - Returns an empty list
        """
        empty_queryset = Mock(spec=QuerySet)
        empty_queryset.__iter__ = Mock(return_value=iter([]))

        result = certificate_by_org(empty_queryset, "edX")

        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, list)

    def test_filter_single_certificate(self):
        """
        Test filtering a QuerySet with only one certificate.

        Expected result:
        - Returns the certificate if it matches the organization
        """
        single_cert_queryset = Mock(spec=QuerySet)
        single_cert_queryset.__iter__ = Mock(return_value=iter([self.cert1]))

        result = certificate_by_org(single_cert_queryset, "edX")

        self.assertEqual(len(result), 1)
        self.assertIn(self.cert1, result)

    def test_filter_all_certificates_same_org(self):
        """
        Test filtering when all certificates have the same organization.

        Expected result:
        - Returns all certificates when they all match the organization
        """
        # Create certificates with same org
        cert_same_org1 = Certificate(User())
        cert_same_org1.course_id = cert_same_org1.course_id.replace(org="TestOrg")
        cert_same_org2 = Certificate(User())
        cert_same_org2.course_id = cert_same_org2.course_id.replace(org="TestOrg")

        same_org_queryset = Mock(spec=QuerySet)
        same_org_queryset.__iter__ = Mock(return_value=iter([cert_same_org1, cert_same_org2]))

        result = certificate_by_org(same_org_queryset, "TestOrg")

        self.assertEqual(len(result), 2)
        self.assertIn(cert_same_org1, result)
        self.assertIn(cert_same_org2, result)


class TestCertificateByCourseIdRegexFilter(TestCase):
    """
    Test the certificate_by_course_id_regex filter function.
    """

    def setUp(self):
        """Set up test data."""
        self.user1 = User()
        self.user2 = User()
        self.user3 = User()

        # Create certificates with different course IDs
        self.cert1 = Certificate(self.user1)
        self.cert1.course_id = self.cert1.course_id.replace(course="CS101")

        self.cert2 = Certificate(self.user2)
        self.cert2.course_id = self.cert2.course_id.replace(course="MATH201")

        self.cert3 = Certificate(self.user3)
        self.cert3.course_id = self.cert3.course_id.replace(course="CS102")

        # Create a mock QuerySet
        self.certificates = Mock(spec=QuerySet)
        self.certificates.filter.return_value = self.certificates

    def test_filter_by_course_pattern(self):
        """
        Test filtering certificates by course pattern using regex.

        Expected result:
        - Returns a filtered QuerySet
        """
        result = certificate_by_course_id_regex(self.certificates, r"CS\d+")

        self.certificates.filter.assert_called_once_with(course_id__regex=r"CS\d+")
        self.assertEqual(result, self.certificates)

    def test_filter_by_exact_course_match(self):
        """
        Test filtering certificates by exact course match.

        Expected result:
        - Returns a filtered QuerySet
        """
        result = certificate_by_course_id_regex(self.certificates, r"CS101")

        self.certificates.filter.assert_called_once_with(course_id__regex=r"CS101")
        self.assertEqual(result, self.certificates)

    def test_filter_by_nonexistent_pattern(self):
        """
        Test filtering certificates by a pattern that doesn't match any course.

        Expected result:
        - Returns a filtered QuerySet
        """
        result = certificate_by_course_id_regex(self.certificates, r"PHYS\d+")

        self.certificates.filter.assert_called_once_with(course_id__regex=r"PHYS\d+")
        self.assertEqual(result, self.certificates)

    def test_filter_by_case_insensitive_pattern(self):
        """
        Test filtering certificates with case insensitive pattern.

        Expected result:
        - Returns a filtered QuerySet
        """
        result = certificate_by_course_id_regex(self.certificates, r"[Cc][Ss]\d+")

        self.certificates.filter.assert_called_once_with(course_id__regex=r"[Cc][Ss]\d+")
        self.assertEqual(result, self.certificates)

    def test_filter_empty_certificates_list(self):
        """
        Test filtering an empty QuerySet of certificates.

        Expected result:
        - Returns a filtered QuerySet
        """
        empty_queryset = Mock(spec=QuerySet)
        empty_queryset.filter.return_value = empty_queryset

        result = certificate_by_course_id_regex(empty_queryset, r"CS\d+")

        empty_queryset.filter.assert_called_once_with(course_id__regex=r"CS\d+")
        self.assertEqual(result, empty_queryset)

    def test_filter_by_complex_regex_pattern(self):
        """
        Test filtering certificates by a complex regex pattern.

        Expected result:
        - Returns a filtered QuerySet
        """
        complex_queryset = Mock(spec=QuerySet)
        complex_queryset.filter.return_value = complex_queryset

        result = certificate_by_course_id_regex(complex_queryset, r"CS\d+.*Advanced")

        complex_queryset.filter.assert_called_once_with(course_id__regex=r"CS\d+.*Advanced")
        self.assertEqual(result, complex_queryset)

    def test_filter_by_org_and_course_pattern(self):
        """
        Test filtering certificates by organization and course pattern.

        Expected result:
        - Returns a filtered QuerySet
        """
        org_course_queryset = Mock(spec=QuerySet)
        org_course_queryset.filter.return_value = org_course_queryset

        result = certificate_by_course_id_regex(org_course_queryset, r"edX.*CS\d+")

        org_course_queryset.filter.assert_called_once_with(course_id__regex=r"edX.*CS\d+")
        self.assertEqual(result, org_course_queryset)

    def test_filter_with_special_regex_characters(self):
        """
        Test filtering certificates with special regex characters in course IDs.

        Expected result:
        - Properly handles special regex characters
        """
        special_queryset = Mock(spec=QuerySet)
        special_queryset.filter.return_value = special_queryset

        result = certificate_by_course_id_regex(special_queryset, r"CS101\+Advanced")

        special_queryset.filter.assert_called_once_with(course_id__regex=r"CS101\+Advanced")
        self.assertEqual(result, special_queryset)

    def test_filter_invalid_regex_pattern(self):
        """
        Test filtering certificates with an invalid regex pattern.

        Expected result:
        - Raises re.error for invalid regex patterns
        """
        self.certificates.filter.side_effect = re.error("Invalid regex")

        with self.assertRaises(re.error):
            certificate_by_course_id_regex(self.certificates, r"[invalid")

    def test_filter_by_full_course_id_pattern(self):
        """
        Test filtering certificates by full course ID pattern.

        Expected result:
        - Returns a filtered QuerySet
        """
        result = certificate_by_course_id_regex(self.certificates, r"course-v1:.*CS\d+")

        self.certificates.filter.assert_called_once_with(course_id__regex=r"course-v1:.*CS\d+")
        self.assertEqual(result, self.certificates)
