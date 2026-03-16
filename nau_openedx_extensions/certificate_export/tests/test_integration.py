"""
Integration tests for the Student Answers Values Report API endpoint.
"""

from unittest.mock import MagicMock, patch

from common.djangoapps.student.roles import CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory
from django.test import TransactionTestCase
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from rest_framework import status
from rest_framework.test import APIClient

VIEWS_MODULE_PATH = "nau_openedx_extensions.certificate_export.views"


class StudentAnswersReportAPIIntegrationTest(TransactionTestCase):
    """
    Integration tests for the StudentAnswersValuesReportAPIView endpoint.

    Uses real Django users, courses, and role assignments to test the full
    API flow from HTTP request through permission checks to task dispatch.
    """

    def setUp(self):
        """Set up test fixtures with real database objects."""
        self.client = APIClient()
        self.course = CourseOverviewFactory()
        self.course_id = str(self.course.id)
        self.block_id = (
            f"block-v1:{self.course.id.org}+{self.course.id.course}"
            f"+{self.course.id.run}+type@problem+block@problem1"
        )
        self.endpoint = (
            f"/nau-openedx-extensions/certificate-export/courses"
            f"/{self.course_id}/student-answers-values"
        )

        self.staff_user = UserFactory()
        CourseStaffRole(self.course.id).add_users(self.staff_user)

        self.regular_user = UserFactory()

    @patch(f"{VIEWS_MODULE_PATH}.student_answers_values_report_task")
    def test_staff_user_can_trigger_report(self, mock_task):
        """
        A user with CourseStaffRole can successfully trigger
        the student answers values report task via the API.
        """
        mock_task.delay.return_value = MagicMock()

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post(
            self.endpoint,
            data={"block_id": self.block_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        mock_task.delay.assert_called_once_with(self.course_id, self.block_id)

    def test_non_staff_user_is_denied(self):
        """
        A regular user without CourseStaffRole or CourseDataResearcherRole
        is denied access to the endpoint.
        """
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(
            self.endpoint,
            data={"block_id": self.block_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch(f"{VIEWS_MODULE_PATH}.student_answers_values_report_task")
    def test_missing_block_id_returns_400(self, mock_task):
        """
        A staff user sending a POST without block_id
        receives a 400 Bad Request response.
        """
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post(
            self.endpoint,
            data={},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        mock_task.delay.assert_not_called()

    def test_invalid_course_id_returns_400(self):
        """
        An invalid course_id in the URL returns 400.
        """
        invalid_endpoint = (
            "/nau-openedx-extensions/certificate-export/courses"
            "/not-a-valid-course/student-answers-values"
        )

        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post(
            invalid_endpoint,
            data={"block_id": self.block_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch(f"{VIEWS_MODULE_PATH}.student_answers_values_report_task")
    def test_task_receives_correct_parameters(self, mock_task):
        """
        The dispatched task receives exactly the course_id and block_id
        that were sent in the API request.
        """
        mock_task.delay.return_value = MagicMock()

        self.client.force_authenticate(user=self.staff_user)
        self.client.post(
            self.endpoint,
            data={"block_id": self.block_id},
            format="json",
        )

        args = mock_task.delay.call_args[0]
        self.assertEqual(args[0], self.course_id)
        self.assertEqual(args[1], self.block_id)

    @patch(f"{VIEWS_MODULE_PATH}.student_answers_values_report_task")
    def test_unauthenticated_user_is_denied(self, mock_task):
        """
        An unauthenticated request is denied access.
        """
        response = self.client.post(
            self.endpoint,
            data={"block_id": self.block_id},
            format="json",
        )

        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        mock_task.delay.assert_not_called()
