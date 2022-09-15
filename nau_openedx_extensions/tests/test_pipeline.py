"""
Tests for the pipeline module used in nau_openex_extensions
"""

from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.filters.pipeline import FilterEnrollmentByDomain


@patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
class FilterEnrollmentByDomainTest(TestCase):
    """Test"""

    def setUp(self):
        self.course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        self.user = MagicMock(email="example@example.com")
        self.mode = "audit"

    def test_user_is_allowed_to_enroll_for_allowed_domain(self, get_other_course_settings_mock):
        """Test"""

        get_other_course_settings_mock.return_value = {"domains_allowed": ["example.com"]}

        response = FilterEnrollmentByDomain.run_filter(self, self.user, self.course_key, self.mode)

        get_other_course_settings_mock.assert_called_once_with(self.course_key)
        self.assertEqual(response, {})


    def test_user_is_allowed_to_enroll_for_no_other_course_setting(self, get_other_course_settings_mock):
        """Test"""

        course_other_course_settings = Mock()
        get_other_course_settings_mock.return_value = course_other_course_settings
        course_other_course_settings.get.return_value = []

        response = FilterEnrollmentByDomain.run_filter(self, self.user, self.course_key, self.mode)

        get_other_course_settings_mock.assert_called_once_with(self.course_key)
        course_other_course_settings.get.assert_called_once_with('domains_allowed', [])
        self.assertEqual(response, {})


    def test_user_is_not_allowed_to_enroll(self, get_other_course_settings_mock):
        """Test"""

        get_other_course_settings_mock.return_value = {"domains_allowed": ["test.com"]}

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            FilterEnrollmentByDomain.run_filter(self, self.user, self.course_key, self.mode)
            get_other_course_settings_mock.assert_called_once_with(self.course_key)