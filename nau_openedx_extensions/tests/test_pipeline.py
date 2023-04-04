"""
Tests for the pipeline module used in nau_openex_extensions
"""

from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from django.test.utils import override_settings
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.filters.pipeline import FilterEnrollmentByDomain


class FilterEnrollmentByDomainTest(TestCase):
    """
    Test the FilterEnrollmentByDomain that prevent enrollment if the email domain is not allowed.
    """

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_for_allowed_domain(self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when user has a domain that is allowed in the other course settings.

        Expected result:
        - The get other course settings is called once with the course key.
        - The other_course_settings.get is called once with value and {}
        - The other_course_settings.get calls get with filter_enrollment_by_domain_list and []
        - The function fnmatch is called with a user_domain and a domain
        - The filter returns {} that means that the user is allowed to enroll.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["example.com"]
        other_course_settings = Mock()
        get_other_course_settings_mock.return_value = other_course_settings
        other_course_settings_get = Mock()
        other_course_settings.get.return_value = other_course_settings_get
        other_course_settings_get.get.return_value = allowed_domains_list
        fnmatch_mock.return_value = True

        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)

        get_other_course_settings_mock.assert_called_once_with(course_key)
        other_course_settings.get.assert_called_once_with("value", {})
        other_course_settings_get.get.assert_called_once_with("filter_enrollment_by_domain_list")
        fnmatch_mock.assert_not_called()
        self.assertEqual(response, {})

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_for_allowed_domain_with_subdomain(
            self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when user has a subdomain that is allowed in the other course settings.

        Expected result:
        - The fnmatch is called with the all subdomain and a domain
        - The filter returns {} that means that the user is allowed to enroll.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["example.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        user = MagicMock(email="example@subdomain.example.com")
        fnmatch_mock.return_value = True
        user_domain = user.email.split("@")[1]

        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)

        fnmatch_mock.assert_called_once_with(user_domain, f"*.{allowed_domains_list[0]}")
        self.assertEqual(response, {})

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_for_no_other_course_setting(self, get_other_course_settings_mock, fnmatch_mock):
        """Test the filter when the course dont have other course settings for filter_enrollment_by_domain_list.

        Expected result:
        - The fnmatch not called
        - The filter returns {} that means that the user is allowed to enroll."""
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        get_other_course_settings_mock.return_value = {}

        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)

        fnmatch_mock.assert_not_called()
        self.assertEqual(response, {})

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_not_allowed_to_enroll(self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when exists the other course settings with filter_enrollment_by_domain_list,
        but the user is not allowed to enroll because the domain is not in the settings.

        Expected result:
        - PreventEnrollment exception has raised
        - The fnmatch has been called once with the user domain and a domain
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["test.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        fnmatch_mock.return_value = False
        user_domain = user.email.split("@")[1]

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
            fnmatch_mock.assert_called_once_with(user_domain, f"*.{allowed_domains_list[0]}")

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_not_allowed_to_enroll_similar_email(self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when exists the other course settings with filter_enrollment_by_domain_list,
        but the user is not allowed to enroll because the domain is not in the settings.
        Check it won't match for very similar domains, but it isn't a subdomain.

        Expected result:
        - PreventEnrollment exception has raised
        - The fnmatch has been called once with the user domain and a domain
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["xample.com", "eexample.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        fnmatch_mock.return_value = False
        user_domain = user.email.split("@")[1]

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
            fnmatch_mock.assert_called_once_with(user_domain, f"*.{allowed_domains_list[0]}")

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    @override_settings(PLATFORM_NAME='NAU')
    def test_require_user_to_activate_account_for_filter_enrollment_by_domain(
            self, get_other_course_settings_mock):
        """
        Test the filter when the course has a configuration in the other course settings
        that should filter enrollment by user email domain,
        the user email matches one of the allowed domains,
        but he hasn't activated its account.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=False)
        mode = "audit"

        allowed_domains_list = ["xample.com", "example.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as pe:
            FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
        self.assertEqual(pe.exception.message, (
            "You need to activate your account before you can enroll in the course. "
            "Check your example@example.com inbox for an account activation link from NAU."
        ))

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_require_user_to_activate_account_for_enrollment_course_no_config_user_active(
            self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when the course hasn't a configuration in the other course settings
        and the user has an activated account.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        get_other_course_settings_mock.return_value = {"value": {}}
        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
        self.assertEqual(response, {})
        fnmatch_mock.assert_not_called()

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_require_user_to_activate_account_for_enrollment_course_no_config_user_inactive(
            self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when the course has a configuration in the other course settings
        and the user hasn't an activated account.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=False)
        mode = "audit"

        get_other_course_settings_mock.return_value = {"value": {}}
        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
        self.assertEqual(response, {})
        fnmatch_mock.assert_not_called()

    @patch('nau_openedx_extensions.filters.pipeline.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_email_not_in_allowed_domains_to_enroll_but_with_course_enrollment_allowed(
            self, get_other_course_settings_mock, fnmatch_mock, get_student_course_enrollment_allowed_mock):
        """
        Test the filter when the user email in not in the allowed domains for self enroll, but the
        user email have been manualy added as a course enrollment allowed.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["xample.com", "eexample.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        get_student_course_enrollment_allowed_mock.return_value = object()

        FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)

        get_student_course_enrollment_allowed_mock.assert_called_once_with(user, course_key)
        fnmatch_mock.assert_not_called()

    @override_settings(PLATFORM_NAME='NAU')
    def test_inactive_user_with_email_not_in_allowed_domains(self):
        """
        Test the filter when the user is inactive and the user email domain isn't an allowed
        domain and check that it failing with the error message related that the user needs to
        activate their account.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=False)
        mode = "audit"

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as pe:
            FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
        self.assertEqual(pe.exception.message, (
            "You need to activate your account before you can enroll in the course. "
            "Check your example@example.com inbox for an account activation link from NAU."
        ))
