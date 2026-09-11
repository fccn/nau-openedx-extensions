"""
Unit tests for survey export views.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from nau_openedx_extensions.certificate_export.views import INVALID_COURSE_MESSAGE
from nau_openedx_extensions.survey_export.views import SUCCESS_MESSAGE, SurveyExportAPIView

VIEWS_MODULE_PATH = "nau_openedx_extensions.survey_export.views"

validate_course_access_patch = patch(f"{VIEWS_MODULE_PATH}.validate_course_access")
export_surveys_task_patch = patch(f"{VIEWS_MODULE_PATH}.export_course_surveys_task")


class SurveyExportAPIViewTest(APITestCase):
    """Test cases for SurveyExportAPIView (Survey components CSV export)."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.factory = APIRequestFactory()
        self.course_id = "course-v1:NAU+Demo+DemoCourse"
        self.view = SurveyExportAPIView.as_view()

        # Create a test user
        self.user = MagicMock()
        self.user.is_staff = False
        self.user.is_authenticated = True

    def _make_request(self, course_id: str | None = None) -> Any:
        """Make a POST request to the survey export endpoint."""
        course_id = course_id or self.course_id
        url = f"nau-openedx-extensions/survey-export/courses/{course_id}/csv"
        request = self.factory.post(url)
        force_authenticate(request, user=self.user)
        return self.view(request, course_id=course_id)

    @export_surveys_task_patch
    @validate_course_access_patch
    def test_successful_survey_export_starts_task(
        self,
        validate_course_access_mock: MagicMock,
        export_surveys_task_mock: MagicMock,
    ):
        """Test that a user with course access starts the survey export task asynchronously."""
        validate_course_access_mock.return_value = (True, CourseKey.from_string(self.course_id))

        response = self._make_request()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"success": True, "message": SUCCESS_MESSAGE})
        export_surveys_task_mock.delay.assert_called_once_with(self.course_id)
        export_surveys_task_mock.assert_not_called()

    @export_surveys_task_patch
    @validate_course_access_patch
    def test_survey_export_without_access_returns_validation_response(
        self,
        validate_course_access_mock: MagicMock,
        export_surveys_task_mock: MagicMock,
    ):
        """Test that the access check response is returned and no task is started."""
        no_access_response = Response({"success": False}, status=status.HTTP_401_UNAUTHORIZED)
        validate_course_access_mock.return_value = (False, no_access_response)

        response = self._make_request()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data, {"success": False})
        export_surveys_task_mock.delay.assert_not_called()

    @export_surveys_task_patch
    def test_survey_export_invalid_course_id(self, export_surveys_task_mock: MagicMock):
        """Test survey export with invalid course ID, using the real access check."""
        response = self._make_request("invalid-course-id")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["course_id"], INVALID_COURSE_MESSAGE)
        export_surveys_task_mock.delay.assert_not_called()

    def test_survey_export_unauthenticated_access(self):
        """Test survey export when user is not authenticated."""
        self.user.is_authenticated = False
        response = self._make_request()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
