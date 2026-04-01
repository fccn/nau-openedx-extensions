"""
Unit tests for course_filters.handlers module.
"""

from unittest.mock import patch

from django.test import TestCase
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.course_filters.handlers import course_published_handler

HANDLERS_PATH = "nau_openedx_extensions.course_filters.handlers"

COURSE_ID = "course-v1:Demo+DemoX+Demo_Course"


class CoursePublishedHandlerTest(TestCase):
    """Tests for course_published_handler()."""

    def setUp(self):
        self.course_key = CourseKey.from_string(COURSE_ID)

    @patch(f"{HANDLERS_PATH}.sync_course_filters_for_course")
    @patch(f"{HANDLERS_PATH}.log")
    def test_handler_calls_sync_and_logs(self, mock_log, mock_sync):
        """
        Handler calls sync_course_filters_for_course and logs the result.
        """
        mock_sync.return_value = {"created": 2, "deleted": 0, "unchanged": 1}

        course_published_handler(course_key=self.course_key)

        mock_sync.assert_called_once_with(self.course_key)
        mock_log.info.assert_called()

    @patch(f"{HANDLERS_PATH}.sync_course_filters_for_course")
    @patch(f"{HANDLERS_PATH}.log")
    def test_handler_does_not_raise_on_sync_error(self, mock_log, mock_sync):
        """
        If sync_course_filters_for_course raises (which it shouldn't by design), the handler
        does not propagate the exception so course publishing is never blocked.
        """
        mock_sync.side_effect = Exception("Unexpected failure")

        try:
            course_published_handler(course_key=self.course_key)
        except Exception:  # pylint: disable=broad-except
            self.fail("course_published_handler raised an exception unexpectedly")

    @patch(f"{HANDLERS_PATH}.sync_course_filters_for_course")
    @patch(f"{HANDLERS_PATH}.log")
    def test_handler_passes_extra_kwargs(self, mock_log, mock_sync):
        """
        Handler accepts **kwargs from the signal dispatcher without errors.
        """
        mock_sync.return_value = {"created": 0, "deleted": 0, "unchanged": 0}

        course_published_handler(course_key=self.course_key, sender=None, signal=None)

        mock_sync.assert_called_once_with(self.course_key)
