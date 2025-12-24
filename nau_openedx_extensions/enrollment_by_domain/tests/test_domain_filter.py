"""
Unit tests for FilterEnrollmentByAllowedList domain filter.

These tests verify the enrollment filtering logic based on email domains,
including configuration, user account status, instructor overrides, domain
validation, and error message handling.
"""

from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.enrollment_by_domain.domain_filter import FilterEnrollmentByAllowedList
from nau_openedx_extensions.enrollment_by_domain.models import EnrollmentAllowedDomain, EnrollmentAllowedList


class FilterEnrollmentByAllowedListTest(TestCase):
    """
    Test suite for FilterEnrollmentByAllowedList filter.

    Tests cover:
    - Filter activation and configuration
    - User account status validation
    - Instructor override behavior
    - Already enrolled user handling
    - Domain validation (exact and subdomain matching)
    - Error message priority system
    - Edge cases and error handling
    - Logging behavior
    """

    def setUp(self):
        """Set up test fixtures."""
        # PipelineStep requires filter_type and running_pipeline arguments
        self.filter = FilterEnrollmentByAllowedList(
            filter_type=Mock(),
            running_pipeline=[]
        )
        self.course_key = CourseKey.from_string("course-v1:Org+Course+Run")
        self.mode = "audit"

    def _create_mock_user(self, email, is_active=True, username="testuser"):
        """Helper to create a mock user object."""
        user = Mock()
        user.email = email
        user.is_active = is_active
        user.username = username
        return user

    # ========================================================================
    # 1. FILTER ACTIVATION & CONFIGURATION TESTS
    # ========================================================================

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_no_filter_configured_allows_enrollment(self, mock_get_settings):
        """
        Test that enrollment proceeds when no filter is configured.

        When the course doesn't have filter_enrollment_allowed_list_code
        in its settings, the filter should allow enrollment without checks.
        """
        mock_get_settings.return_value = {"value": {}}
        user = self._create_mock_user("user@example.com")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})
        mock_get_settings.assert_called_once_with(self.course_key)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_filter_configured_with_camelcase_setting(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that filter activates with camelCase setting name.

        The filter should recognize 'filterEnrollmentAllowedListCode'
        (camelCase format used in some OpenEdX versions).
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            description="Test list"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filterEnrollmentAllowedListCode": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.edu")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_filter_configured_with_snake_case_setting(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that filter activates with snake_case setting name.

        The filter should recognize 'filter_enrollment_allowed_list_code'
        (snake_case format).
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            description="Test list"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.edu")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_enrollment_allowed_list_does_not_exist(self, mock_get_settings, mock_cea):
        """
        Test graceful degradation when EnrollmentAllowedList doesn't exist.

        If the configured list code doesn't exist in the database, the filter
        should log an error but allow enrollment (fail open for safety).
        """
        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "nonexistent-list"}
        }
        mock_cea.return_value = None
        user = self._create_mock_user("user@example.com")

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='ERROR') as logs:
            result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})
        self.assertTrue(any("not found" in log for log in logs.output))

    # ========================================================================
    # 2. USER ACCOUNT STATUS TESTS
    # ========================================================================

    @override_settings(PLATFORM_NAME='TestPlatform')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.configuration_helpers')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_inactive_user_blocked_with_activation_message(self, mock_get_settings, mock_config_helpers):
        """
        Test that inactive users are blocked with activation message.

        Users who haven't activated their accounts should be prevented from
        enrolling with a message directing them to activate their account.
        """
        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_config_helpers.get_value.return_value = "TestPlatform"

        user = self._create_mock_user("user@example.com", is_active=False)

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        exception_msg = str(context.exception.message)
        self.assertIn("activate your account", exception_msg)
        self.assertIn("user@example.com", exception_msg)
        self.assertIn("TestPlatform", exception_msg)

    @override_settings(PLATFORM_NAME='CustomPlatform')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.configuration_helpers')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_platform_name_customization_in_activation_message(self, mock_get_settings, mock_config_helpers):
        """
        Test that platform name is correctly included in activation message.

        The activation message should use the platform name from configuration.
        """
        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_config_helpers.get_value.return_value = "CustomPlatform"

        user = self._create_mock_user("student@school.edu", is_active=False)

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertIn("CustomPlatform", str(context.exception.message))

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_active_user_with_valid_domain_allowed(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that active users with valid domains can enroll.

        Active users whose email domains match the allowed list should be
        able to enroll successfully.
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("student@university.edu", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    # ========================================================================
    # 3. INSTRUCTOR OVERRIDE TESTS
    # ========================================================================

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_instructor_override_allows_non_matching_domain(self, mock_get_settings, mock_cea):
        """
        Test that instructor manual enrollment overrides domain check.

        If an instructor has manually added a user's email to the course
        enrollment allowed list, they should be able to enroll even if
        their domain doesn't match the allowed list.
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        # Simulate instructor has allowed this specific email
        mock_cea.return_value = Mock()  # Non-None value indicates allowed

        user = self._create_mock_user("external@otherdomain.com", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})
        mock_cea.assert_called_once_with(user, self.course_key)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_instructor_override_with_matching_domain(self, mock_get_settings, mock_cea):
        """
        Test early exit when instructor override exists with matching domain.

        When both instructor override and domain match exist, the filter
        should exit early via the instructor check (optimization).
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = Mock()  # Instructor override exists

        user = self._create_mock_user("student@university.edu", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})
        # Should exit early, not checking domain
        mock_cea.assert_called_once()

    # ========================================================================
    # 4. ALREADY ENROLLED TESTS
    # ========================================================================

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_already_enrolled_user_domain_check_skipped(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that already enrolled users skip domain validation.

        Users who are already enrolled in the course should be allowed to
        proceed without domain validation (e.g., for mode changes).
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = Mock()  # User is enrolled

        # User with non-matching domain who is already enrolled
        user = self._create_mock_user("user@otherdomain.com", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})
        mock_enrollment.assert_called_once_with(user, self.course_key)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_already_enrolled_user_with_matching_domain(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that enrolled users with matching domains are allowed.

        Even when domain matches, enrolled users should proceed without
        additional validation.
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = Mock()

        user = self._create_mock_user("student@university.edu", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    # ========================================================================
    # 5. DOMAIN VALIDATION TESTS (via run_filter)
    # ========================================================================

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_exact_domain_match_allowed(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test exact domain matching.

        Email: user@university.edu
        Allowed: university.edu
        Expected: Enrollment allowed (exact match)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.edu")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_subdomain_match_allowed(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test subdomain matching with fnmatch.

        Email: student@cs.university.edu
        Allowed: university.edu
        Expected: Enrollment allowed (subdomain match)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("student@cs.university.edu")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_multi_level_subdomain_match_allowed(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test multi-level subdomain matching.

        Email: user@dept.faculty.university.edu
        Allowed: university.edu
        Expected: Enrollment allowed (multi-level subdomain match)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@dept.faculty.university.edu")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_domain_not_in_allowed_list(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that non-matching domains are rejected.

        Email: user@other.com
        Allowed: university.edu
        Expected: Enrollment blocked
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            self.filter.run_filter(user, self.course_key, self.mode)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_similar_but_different_domain_not_allowed(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that similar domains don't match (no partial matching).

        Email: user@other-university.edu
        Allowed: university.edu
        Expected: Enrollment blocked (not a subdomain, different domain)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other-university.edu")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            self.filter.run_filter(user, self.course_key, self.mode)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_invalid_email_format_no_at_symbol(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test handling of invalid email format (no @ symbol).

        Email: invalid-email
        Expected: Enrollment blocked with warning log
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("invalid-email")

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='WARNING'):
            with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
                self.filter.run_filter(user, self.course_key, self.mode)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_empty_email(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test handling of empty email.

        Email: ""
        Expected: Enrollment blocked with warning log
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("")

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='WARNING'):
            with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
                self.filter.run_filter(user, self.course_key, self.mode)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_case_insensitive_domain_matching(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that domain matching is case-insensitive.

        Email: user@UNIVERSITY.EDU
        Allowed: university.edu
        Expected: Enrollment allowed (case-insensitive match)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@UNIVERSITY.EDU")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_multiple_domains_first_matches(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test multiple domains in allowed list (first matches).

        Email: user@university.edu
        Allowed: [university.edu, college.edu]
        Expected: Enrollment allowed (matches first domain)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="college.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.edu")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_multiple_domains_second_matches(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test multiple domains in allowed list (second matches).

        Email: user@college.edu
        Allowed: [university.edu, college.edu]
        Expected: Enrollment allowed (matches second domain)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="college.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@college.edu")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_domain_with_whitespace_stripped(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that domains with whitespace are properly handled.

        Email: user@university.edu
        Allowed: " university.edu " (with spaces)
        Expected: Enrollment allowed (whitespace stripped during comparison)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain=" university.edu "
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.edu")

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_none_email(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test handling of None email.

        Email: None
        Expected: Enrollment blocked with warning log
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = Mock()
        user.email = None
        user.username = "testuser"
        user.is_active = True

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='WARNING'):
            with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
                self.filter.run_filter(user, self.course_key, self.mode)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_empty_allowed_domains_list(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test behavior when allowed domains list is empty.

        Allowed: [] (empty list)
        Expected: Enrollment blocked (no domains to match against)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        # No domains added to the list

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.edu")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            self.filter.run_filter(user, self.course_key, self.mode)

    # ========================================================================
    # 6. ERROR MESSAGE PRIORITY TESTS (via run_filter)
    # ========================================================================

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_message_priority_course_level_camelcase(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that course-level custom message (camelCase) has highest priority.

        Priority 1: Course-level message (filterEnrollmentByDomainCustomExceptionMessage)
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            custom_exception_message="List-level message"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_allowed_list_code": "test-list",
                "filterEnrollmentByDomainCustomExceptionMessage": "Course-level camelCase message"
            }
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(str(context.exception.message), "Course-level camelCase message")

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_message_priority_course_level_snake_case(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that course-level custom message (snake_case) has highest priority.

        Priority 1: Course-level message (filter_enrollment_by_domain_custom_exception_message)
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            custom_exception_message="List-level message"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_allowed_list_code": "test-list",
                "filter_enrollment_by_domain_custom_exception_message": "Course-level snake_case message"
            }
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(str(context.exception.message), "Course-level snake_case message")

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_message_priority_list_level(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that list-level message is used when no course-level message.

        Priority 2: List-level message (from EnrollmentAllowedList model)
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            custom_exception_message="List-level custom message"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(str(context.exception.message), "List-level custom message")

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_message_priority_default(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that default message is used when no custom messages exist.

        Priority 3: Default hardcoded message
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            custom_exception_message=""
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        # Check that default message is returned
        message = str(context.exception.message).lower()
        self.assertIn("can't enroll", message)
        self.assertIn("email domain", message)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_message_empty_course_level_falls_back_to_list(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that empty course-level message falls back to list-level.

        Empty or whitespace-only course messages should be ignored.
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            custom_exception_message="List-level message"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_allowed_list_code": "test-list",
                "filter_enrollment_by_domain_custom_exception_message": "   "
            }
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(str(context.exception.message), "List-level message")

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_message_empty_list_level_falls_back_to_default(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that empty list-level message falls back to default.

        Empty or whitespace-only list messages should be ignored.
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            custom_exception_message="   "
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        message = str(context.exception.message).lower()
        self.assertIn("can't enroll", message)

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_message_whitespace_only_treated_as_empty(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that whitespace-only messages are treated as empty.

        Messages with only spaces, tabs, or newlines should fall back.
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            custom_exception_message="Real message"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_allowed_list_code": "test-list",
                "filter_enrollment_by_domain_custom_exception_message": "\t\n  \n\t"
            }
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(str(context.exception.message), "Real message")

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_message_snake_case_takes_precedence_over_camelcase(
        self, mock_get_settings, mock_cea, mock_enrollment
    ):
        """
        Test priority when both camelCase and snake_case are present.

        When both formats exist, camelCase should be checked first (or condition).
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="test-list",
            custom_exception_message="List message"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_allowed_list_code": "test-list",
                "filterEnrollmentByDomainCustomExceptionMessage": "CamelCase message",
                "filter_enrollment_by_domain_custom_exception_message": "Snake_case message"
            }
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@other.com")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        # The 'or' operator means camelCase is evaluated first
        self.assertEqual(str(context.exception.message), "CamelCase message")

    # ========================================================================
    # 7. INTEGRATION/END-TO-END TESTS
    # ========================================================================

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_complete_successful_enrollment_flow(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test complete successful enrollment flow.

        Active user with matching domain should successfully complete all
        filter checks and be allowed to enroll.
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="university-partners",
            description="University partners list"
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "university-partners"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("student@cs.university.edu", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_complete_blocked_enrollment_flow(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test complete blocked enrollment flow.

        Active user with non-matching domain and no instructor override
        should be blocked from enrolling with appropriate error message.
        """
        allowed_list = EnrollmentAllowedList.objects.create(
            code="university-partners",
            custom_exception_message="Only university partners can enroll."
        )
        EnrollmentAllowedDomain.objects.create(
            allowed_list=allowed_list,
            domain="university.edu"
        )

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "university-partners"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@external.com", is_active=True)

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(str(context.exception.message), "Only university partners can enroll.")

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_multiple_domain_checks_with_subdomain_logic(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test complex scenario with multiple allowed domains and subdomain matching.

        Should correctly match against multiple domains with various
        subdomain levels.
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="multi-partners")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university.edu")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="college.org")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="institute.net")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "multi-partners"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        # Test various matching scenarios
        test_cases = [
            ("user@university.edu", True),
            ("student@cs.university.edu", True),
            ("prof@dept.faculty.university.edu", True),
            ("user@college.org", True),
            ("admin@sub.college.org", True),
            ("user@institute.net", True),
            ("user@otherdomain.com", False),
            ("user@college-copy.org", False),
        ]

        for email, should_allow in test_cases:
            user = self._create_mock_user(email, is_active=True)

            if should_allow:
                result = self.filter.run_filter(user, self.course_key, self.mode)
                self.assertEqual(result, {}, f"Email {email} should be allowed")
            else:
                with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
                    self.filter.run_filter(user, self.course_key, self.mode)

    # ========================================================================
    # 8. LOGGING TESTS
    # ========================================================================

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_debug_log_when_instructor_override_applies(self, mock_get_settings, mock_cea):
        """
        Test that debug log is generated when instructor override is used.
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university.edu")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = Mock()

        user = self._create_mock_user("user@external.com", is_active=True)

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='DEBUG') as logs:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertTrue(any("manually allowed by instructor" in log for log in logs.output))

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_debug_log_when_user_already_enrolled(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that debug log is generated when user is already enrolled.
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university.edu")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = Mock()

        user = self._create_mock_user("user@external.com", is_active=True)

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='DEBUG') as logs:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertTrue(any("already enrolled" in log for log in logs.output))

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_info_log_when_enrollment_blocked(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that info log is generated when enrollment is blocked.
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university.edu")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@blocked.com", is_active=True)

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='INFO') as logs:
            with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
                self.filter.run_filter(user, self.course_key, self.mode)

        self.assertTrue(any("Blocked enrollment" in log for log in logs.output))

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_debug_log_when_enrollment_allowed(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that debug log is generated when enrollment is allowed.
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university.edu")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.edu", is_active=True)

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='DEBUG') as logs:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertTrue(any("allowed to enroll" in log for log in logs.output))

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_error_log_when_enrollment_allowed_list_not_found(self, mock_get_settings, mock_cea):
        """
        Test that error log is generated when EnrollmentAllowedList doesn't exist.
        """
        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "nonexistent"}
        }
        mock_cea.return_value = None

        user = self._create_mock_user("user@example.com", is_active=True)

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='ERROR') as logs:
            self.filter.run_filter(user, self.course_key, self.mode)

        self.assertTrue(any("not found" in log for log in logs.output))

    # ========================================================================
    # 9. SPECIAL CASES & EDGE CASES
    # ========================================================================

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_various_enrollment_modes(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test that filter works correctly with various enrollment modes.

        Filter should work regardless of enrollment mode (audit, verified,
        honor, professional, etc.).
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university.edu")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.edu", is_active=True)

        modes = ["audit", "verified", "honor", "professional", "no-id-professional"]

        for mode in modes:
            result = self.filter.run_filter(user, self.course_key, mode)
            self.assertEqual(result, {}, f"Filter should work for mode: {mode}")

    def test_string_representation_methods(self):
        """
        Test __str__ and __repr__ methods of the filter.
        """
        filter_instance = FilterEnrollmentByAllowedList(
            filter_type=Mock(),
            running_pipeline=[]
        )

        str_repr = str(filter_instance)
        repr_repr = repr(filter_instance)

        self.assertIn("FilterEnrollmentByAllowedList", str_repr)
        self.assertIn("FilterEnrollmentByAllowedList", repr_repr)

    @override_settings(PLATFORM_NAME='EdgeCasePlatform')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.configuration_helpers')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_inactive_user_logs_properly(self, mock_get_settings, mock_config_helpers):
        """
        Test that inactive user blocking is logged at INFO level.
        """
        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_config_helpers.get_value.return_value = "EdgeCasePlatform"

        user = self._create_mock_user("user@test.com", is_active=False, username="inactiveuser")

        with self.assertLogs('nau_openedx_extensions.enrollment_by_domain.domain_filter', level='INFO') as logs:
            with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
                self.filter.run_filter(user, self.course_key, self.mode)

        self.assertTrue(any("Blocked enrollment for inactive user" in log for log in logs.output))

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_email_with_special_characters_in_local_part(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test emails with special characters in local part.

        Email: user+tag@university.edu
        Should work correctly (special chars before @)
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university.edu")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user+tag@university.edu", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_domain_with_numbers(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test domains with numbers.

        Email: user@university123.edu
        Should match if domain is in allowed list
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university123.edu")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university123.edu", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})

    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_enrollment')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.enrollment_by_domain.domain_filter.get_other_course_settings')
    def test_international_domain(self, mock_get_settings, mock_cea, mock_enrollment):
        """
        Test international domains (non-.com/.edu/.org).

        Email: user@university.ac.uk
        Should work with international TLDs
        """
        allowed_list = EnrollmentAllowedList.objects.create(code="test-list")
        EnrollmentAllowedDomain.objects.create(allowed_list=allowed_list, domain="university.ac.uk")

        mock_get_settings.return_value = {
            "value": {"filter_enrollment_allowed_list_code": "test-list"}
        }
        mock_cea.return_value = None
        mock_enrollment.return_value = None

        user = self._create_mock_user("user@university.ac.uk", is_active=True)

        result = self.filter.run_filter(user, self.course_key, self.mode)

        self.assertEqual(result, {})
