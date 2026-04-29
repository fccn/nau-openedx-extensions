"""
Tests for CourseEnrollmentAllowed guard when filter_enrollment_require_nif is on.
"""

from unittest import TestCase
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ValidationError

if not settings.configured:
    settings.configure(USE_I18N=False, SECRET_KEY="test-course-enrollment-allowed-nif-guard")
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.course_enrollment_allowed_guard import (
    enforce_no_course_enrollment_allowed_when_nif_required,
)


class EnforceNoCeaWhenNifRequiredTest(TestCase):
    """Unit tests for enforce_no_course_enrollment_allowed_when_nif_required."""

    def setUp(self):
        super().setUp()
        self.course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")

    @patch("nau_openedx_extensions.course_enrollment_allowed_guard.get_other_course_settings")
    def test_ok_when_no_nif_setting(self, mock_get):
        mock_get.return_value = {"value": {}}
        enforce_no_course_enrollment_allowed_when_nif_required(self.course_key)
        mock_get.assert_called_once_with(self.course_key)

    @patch("nau_openedx_extensions.course_enrollment_allowed_guard.get_other_course_settings")
    def test_ok_when_nif_filter_false(self, mock_get):
        mock_get.return_value = {"value": {"filter_enrollment_require_nif": False}}
        enforce_no_course_enrollment_allowed_when_nif_required(self.course_key)

    @patch("nau_openedx_extensions.course_enrollment_allowed_guard.get_other_course_settings")
    def test_raises_when_nif_filter_true(self, mock_get):
        mock_get.return_value = {"value": {"filter_enrollment_require_nif": True}}
        with self.assertRaises(ValidationError):
            enforce_no_course_enrollment_allowed_when_nif_required(self.course_key)

    @patch("nau_openedx_extensions.course_enrollment_allowed_guard.get_other_course_settings")
    def test_ok_when_course_id_none(self, mock_get):
        enforce_no_course_enrollment_allowed_when_nif_required(None)
        mock_get.assert_not_called()
