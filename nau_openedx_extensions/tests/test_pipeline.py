"""
Tests for the pipeline module used in nau_openex_extensions
"""

from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.filters.pipeline import FilterEnrollmentByDomain


@patch('nau_openedx_extensions.filters.pipeline.fnmatch')
@patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
class FilterEnrollmentByDomainTest(TestCase):
    """Test the FilterEnrollmentByDomain that prevent enrollment if the email domain is not allowed."""

    def setUp(self):
        self.course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        self.user = MagicMock(email="example@example.com")
        self.mode = "audit"

    def test_user_is_allowed_to_enroll_for_allowed_domain(self, get_other_course_settings_mock, fnmatch_mock):
        """Test the filter when user has a domain that is allowed in the other course settings.

        Expected result:
        - The get other course settings is called once with the course key.
        - The other_course_settings.get is called once with value and {}
        - The other_course_settings.get calls get with filter_enrollment_by_domain_list and []
        - The function fnmatch is called with a user_domain and a domain
        - The filter returns {} that means that the user is allowed to enroll."""

        allowed_domains_list = ["example.com"]
        other_course_settings = Mock()
        get_other_course_settings_mock.return_value = other_course_settings
        other_course_settings_get = Mock()
        other_course_settings.get.return_value = other_course_settings_get
        other_course_settings_get.get.return_value = allowed_domains_list
        fnmatch_mock.return_value = True
        user_domain = self.user.email.split("@")[1]

        response = FilterEnrollmentByDomain.run_filter(self, self.user, self.course_key, self.mode)

        get_other_course_settings_mock.assert_called_once_with(self.course_key)
        other_course_settings.get.assert_called_once_with("value", {})
        other_course_settings_get.get.assert_called_once_with("filter_enrollment_by_domain_list", [])
        fnmatch_mock.assert_called_once_with(user_domain, f"*{allowed_domains_list[0]}")
        self.assertEqual(response, {})

    def test_user_is_allowed_to_enroll_for_allowed_domain_with_subdomain(
            self, get_other_course_settings_mock, fnmatch_mock):
        """Test the filter when user has a subdomain that is allowed in the other course settings.

        Expected result:
        - The fnmatch is called with the all subdomain and a domain
        - The filter returns {} that means that the user is allowed to enroll."""

        allowed_domains_list = ["example.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        user = MagicMock(email="example@subdomain.example.com")
        fnmatch_mock.return_value = True
        user_domain = user.email.split("@")[1]

        response = FilterEnrollmentByDomain.run_filter(self, user, self.course_key, self.mode)

        fnmatch_mock.assert_called_once_with(user_domain, f"*{allowed_domains_list[0]}")
        self.assertEqual(response, {})

    def test_user_is_allowed_to_enroll_for_no_other_course_setting(self, get_other_course_settings_mock, fnmatch_mock):
        """Test the filter when the course dont have other course settings for filter_enrollment_by_domain_list.

        Expected result:
        - The fnmatch not called
        - The filter returns {} that means that the user is allowed to enroll."""

        get_other_course_settings_mock.return_value = {}

        response = FilterEnrollmentByDomain.run_filter(self, self.user, self.course_key, self.mode)

        fnmatch_mock.assert_not_called()
        self.assertEqual(response, {})

    def test_user_is_not_allowed_to_enroll(self, get_other_course_settings_mock, fnmatch_mock):
        """Test the filter when exists the other course settings with filter_enrollment_by_domain_list,
        but the user is not allowed to enroll because the domain is not in the settings.

        Expected result:
        - PreventEnrollment exception has raised
        - The fnmatch has been called once with the user domain and a domain
        """

        allowed_domains_list = ["test.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        fnmatch_mock.return_value = False
        user_domain = self.user.email.split("@")[1]

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            FilterEnrollmentByDomain.run_filter(self, self.user, self.course_key, self.mode)
            fnmatch_mock.assert_called_once_with(user_domain, f"*{allowed_domains_list[0]}")
