"""
Tests for the extractors modules used in coursecertificate.
"""

from datetime import datetime
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase

from nau_openedx_extensions.coursecertificate.extractors import certificate, course, student
from nau_openedx_extensions.coursecertificate.tests.fixtures import Certificate, User


class TestCertificateExtractor(TestCase):
    """
    Test the certificate extractor functions.
    """

    def setUp(self):
        """Set up test data."""
        self.certificate = Certificate(User())

    def test_date_extractor(self):
        """
        Test the date extractor function.

        Expected result:
        - Returns the certificate created_date in ISO format as string
        """
        result = certificate.date(self.certificate)

        self.assertIsInstance(result, str)
        datetime.fromisoformat(result.replace("Z", "+00:00"))  # Verify it's a valid ISO format date string

    def test_url_extractor(self):
        """
        Test the url extractor function.

        Expected result:
        - Returns the certificate URL using LMS_ROOT_URL and verify_uuid
        """
        result = certificate.url(self.certificate)

        expected_url = f"{settings.LMS_ROOT_URL}/certificates/{self.certificate.verify_uuid}"
        self.assertEqual(result, expected_url)
        self.assertIsInstance(result, str)


class TestCourseExtractor(TestCase):
    """
    Test the course extractor functions.
    """

    def setUp(self):
        """Set up test data."""
        self.certificate = Certificate(User())
        self.course_id = self.certificate.course_id
        self.course_code = self.course_id.course

    def test_id_extractor(self):
        """
        Test the course id extractor function.

        Expected result:
        - Returns the course_id as string
        """
        result = course.id(self.certificate)

        self.assertEqual(result, str(self.certificate.course_id))
        self.assertIsInstance(result, str)

    def test_code_extractor(self):
        """
        Test the course code extractor function.

        Expected result:
        - Returns the course part of the course_id
        """
        result = course.code(self.certificate)

        self.assertEqual(result, self.course_code)
        self.assertIsInstance(result, str)

    @patch("nau_openedx_extensions.coursecertificate.extractors.course.CourseOverview")
    def test_name_extractor(self, mock_course_overview: Mock):
        """
        Test the course name extractor function.

        Expected result:
        - Returns the course display name
        """
        expected_name = f"{self.course_id} display name"
        mock_course = Mock(display_name=expected_name)
        mock_course_overview.objects.get.return_value = mock_course

        result = course.name(self.certificate)

        self.assertEqual(result, expected_name)
        self.assertIsInstance(result, str)


class TestStudentExtractor(TestCase):
    """
    Test the student extractor functions.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User()
        self.certificate = Certificate(self.user)

    def test_email_extractor(self):
        """
        Test the email extractor function.

        Expected result:
        - Returns the user's email address
        """
        result = student.email(self.certificate)

        self.assertEqual(result, self.user.email)
        self.assertIsInstance(result, str)

    def test_username_extractor(self):
        """
        Test the username extractor function.

        Expected result:
        - Returns the user's username
        """
        result = student.username(self.certificate)

        self.assertEqual(result, self.user.username)
        self.assertIsInstance(result, str)

    def test_name_extractor(self):
        """
        Test the name extractor function.

        Expected result:
        - Returns the user's profile name
        """
        result = student.name(self.certificate)

        self.assertEqual(result, self.user.profile.name)
        self.assertIsInstance(result, str)

    def test_nau_user_extended_model_field_with_field(self):
        """
        Test the nau_user_extended_model_field function when user has nauuserextendedmodel.

        Expected result:
        - Returns the value of the specified field from nauuserextendedmodel
        """
        result = student.nau_user_extended_model_field(self.certificate, "nif")

        self.assertEqual(result, self.user.nauuserextendedmodel.nif)

    def test_nau_user_extended_model_field_without_model(self):
        """
        Test the nau_user_extended_model_field function when user doesn't have nauuserextendedmodel.

        Expected result:
        - Returns None when user doesn't have nauuserextendedmodel
        """
        del self.user.nauuserextendedmodel  # Remove the nauuserextendedmodel from the user

        result = student.nau_user_extended_model_field(self.certificate, "nif")

        self.assertIsNone(result)

    def test_nau_user_extended_model_field_nonexistent_field(self):
        """
        Test the nau_user_extended_model_field function with non-existent field.

        Expected result:
        - Returns None when field doesn't exist
        """
        result = student.nau_user_extended_model_field(self.certificate, "nonexistent_field")

        self.assertIsNone(result)

    def test_email_extractor_different_user(self):
        """
        Test the email extractor with different user data.

        Expected result:
        - Returns the correct email for different users
        """
        different_user = User()
        different_user.email = "different@test.edu"
        different_certificate = Certificate(different_user)

        result = student.email(different_certificate)

        self.assertEqual(result, "different@test.edu")

    def test_username_extractor_different_user(self):
        """
        Test the username extractor with different user data.

        Expected result:
        - Returns the correct username for different users
        """
        different_user = User()
        different_user.username = "differentuser"
        different_certificate = Certificate(different_user)

        result = student.username(different_certificate)

        self.assertEqual(result, "differentuser")

    def test_name_extractor_different_user(self):
        """
        Test the name extractor with different user data.

        Expected result:
        - Returns the correct name for different users
        """
        different_user = User()
        different_user.profile.name = "Different User Name"
        different_certificate = Certificate(different_user)

        result = student.name(different_certificate)

        self.assertEqual(result, "Different User Name")

    def test_nau_user_extended_model_field_different_fields(self):
        """
        Test the nau_user_extended_model_field function with different field names.

        Expected result:
        - Returns the correct value for different fields
        """
        # Test different fields
        nif_result = student.nau_user_extended_model_field(self.certificate, "nif")
        cc_result = student.nau_user_extended_model_field(self.certificate, "cc_nic")

        self.assertEqual(nif_result, self.user.nauuserextendedmodel.nif)
        self.assertEqual(cc_result, self.user.nauuserextendedmodel.cc_nic)
