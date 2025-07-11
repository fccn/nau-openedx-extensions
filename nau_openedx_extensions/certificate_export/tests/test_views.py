"""
Unit tests for certificate export views.
"""

from typing import Any
from unittest.mock import MagicMock, patch

from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from nau_openedx_extensions.certificate_export.views import (
    INVALID_COURSE_MESSAGE,
    NO_PERMISSION_MESSAGE,
    SUCCESS_MESSAGE,
    CertificateExportAPIView,
    CertificateExportPdfAPIView,
)

VIEWS_MODULE_PATH = "nau_openedx_extensions.certificate_export.views"

export_certificates_patch = patch(f"{VIEWS_MODULE_PATH}.PDFCommand.handle")
course_staff_role_patch = patch(f"{VIEWS_MODULE_PATH}.CourseStaffRole")
course_instructor_role_patch = patch(f"{VIEWS_MODULE_PATH}.CourseInstructorRole")
course_data_researcher_role_patch = patch(f"{VIEWS_MODULE_PATH}.CourseDataResearcherRole")
export_csv_task_patch = patch(f"{VIEWS_MODULE_PATH}.export_course_certificates_task")


class CertificateExportPdfAPIViewTest(APITestCase):
    """Test cases for CertificateExportPdfAPIView."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.factory = APIRequestFactory()
        self.course_id = "course-v1:NAU+Demo+DemoCourse"
        self.course_key = CourseKey.from_string(self.course_id)
        self.view = CertificateExportPdfAPIView.as_view()

        # Create a test user
        self.user = MagicMock()
        self.user.is_staff = False
        self.user.is_authenticated = True

    def _make_request(self, course_id: str | None = None) -> Any:
        """Make a POST request to the certificate export endpoint."""
        course_id = course_id or self.course_id
        url = f"nau-openedx-extensions/certificate-export/courses/{course_id}/pdf"
        request = self.factory.post(url)
        force_authenticate(request, user=self.user)
        return self.view(request, course_id=course_id)

    def _assert_success_response(self, response: Any) -> None:
        """Assert that the response indicates successful export."""
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], True)
        self.assertEqual(response.data["message"], SUCCESS_MESSAGE)

    def _assert_invalid_course_response(self, response: Any) -> None:
        """Assert the response for an invalid course key."""
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["course_id"], INVALID_COURSE_MESSAGE)

    def _assert_no_permission_response(self, response: Any) -> None:
        """Assert the response for insufficient permissions."""
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["success"], False)
        self.assertEqual(response.data["message"], NO_PERMISSION_MESSAGE)

    @export_certificates_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_successful_export_with_staff_role(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_certificates_mock: MagicMock,
    ):
        """Test successful PDF export when user has staff role."""
        course_staff_role_mock.return_value.has_user.return_value = True
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        export_certificates_mock.return_value = Response(status=status.HTTP_200_OK)

        response = self._make_request()

        self._assert_success_response(response)
        export_certificates_mock.assert_called_once_with(course_ids=[self.course_id])

    @export_certificates_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_successful_export_with_instructor_role(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_certificates_mock: MagicMock,
    ):
        """Test successful PDF export when user has instructor role."""
        course_staff_role_mock.return_value.has_user.return_value = False
        course_instructor_role_mock.return_value.has_user.return_value = True
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        export_certificates_mock.return_value = Response(status=status.HTTP_200_OK)

        response = self._make_request()

        self._assert_success_response(response)
        export_certificates_mock.assert_called_once_with(course_ids=[self.course_id])

    @export_certificates_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_successful_export_with_dataresearcher_role(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_certificates_mock: MagicMock,
    ):
        """Test successful PDF export when user has data researcher role."""
        course_staff_role_mock.return_value.has_user.return_value = False
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = True
        export_certificates_mock.return_value = Response(status=status.HTTP_200_OK)

        response = self._make_request()

        self._assert_success_response(response)
        export_certificates_mock.assert_called_once_with(course_ids=[self.course_id])

    def test_invalid_course_id(self):
        """Test export with invalid course ID."""
        response = self._make_request("invalid-course-id")
        self._assert_invalid_course_response(response)

    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_no_permission(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock
    ):
        """Test export when user has no permissions."""
        course_staff_role_mock.return_value.has_user.return_value = False
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False

        response = self._make_request()
        self._assert_no_permission_response(response)

    def test_unauthenticated_access(self):
        """Test export when user is not authenticated."""
        self.user.is_authenticated = False
        response = self._make_request()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CertificateExportAPIViewTest(APITestCase):
    """Test cases for CertificateExportAPIView (CSV export)."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.factory = APIRequestFactory()
        self.course_id = "course-v1:NAU+Demo+DemoCourse"
        self.course_key = CourseKey.from_string(self.course_id)
        self.view = CertificateExportAPIView.as_view()

        # Create a test user
        self.user = MagicMock()
        self.user.is_staff = False
        self.user.is_authenticated = True

    def _make_request(self, course_id: str | None = None) -> Any:
        """Make a POST request to the CSV certificate export endpoint."""
        course_id = course_id or self.course_id
        url = f"nau-openedx-extensions/certificate-export/courses/{course_id}/csv"
        request = self.factory.post(url)
        force_authenticate(request, user=self.user)
        return self.view(request, course_id=course_id)

    def _assert_success_response(self, response: Any) -> None:
        """Assert that the response indicates successful export."""
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success"], True)
        self.assertEqual(response.data["message"], SUCCESS_MESSAGE)

    def _assert_invalid_course_response(self, response: Any) -> None:
        """Assert the response for an invalid course key."""
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["course_id"], INVALID_COURSE_MESSAGE)

    def _assert_no_permission_response(self, response: Any) -> None:
        """Assert the response for insufficient permissions."""
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["success"], False)
        self.assertEqual(response.data["message"], NO_PERMISSION_MESSAGE)

    @export_csv_task_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_successful_csv_export_with_staff_role(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_csv_task_mock: MagicMock,
    ):
        """Test successful CSV export when user has staff role."""
        course_staff_role_mock.return_value.has_user.return_value = True
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        export_csv_task_mock.delay.return_value = MagicMock()

        response = self._make_request()

        self._assert_success_response(response)
        export_csv_task_mock.delay.assert_called_once_with(self.course_id)

    @export_csv_task_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_successful_csv_export_with_instructor_role(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_csv_task_mock: MagicMock,
    ):
        """Test successful CSV export when user has instructor role."""
        course_staff_role_mock.return_value.has_user.return_value = False
        course_instructor_role_mock.return_value.has_user.return_value = True
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        export_csv_task_mock.delay.return_value = MagicMock()

        response = self._make_request()

        self._assert_success_response(response)
        export_csv_task_mock.delay.assert_called_once_with(self.course_id)

    @export_csv_task_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_successful_csv_export_with_data_researcher_role(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_csv_task_mock: MagicMock,
    ):
        """Test successful CSV export when user has instructor role."""
        course_staff_role_mock.return_value.has_user.return_value = False
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = True
        export_csv_task_mock.delay.return_value = MagicMock()

        response = self._make_request()

        self._assert_success_response(response)
        export_csv_task_mock.delay.assert_called_once_with(self.course_id)

    @export_csv_task_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_successful_csv_export_with_superuser(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_csv_task_mock: MagicMock,
    ):
        """Test successful CSV export when user is superuser/staff."""
        self.user.is_staff = True
        course_staff_role_mock.return_value.has_user.return_value = False
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        export_csv_task_mock.delay.return_value = MagicMock()

        response = self._make_request()

        self._assert_success_response(response)
        export_csv_task_mock.delay.assert_called_once_with(self.course_id)

    def test_csv_export_invalid_course_id(self):
        """Test CSV export with invalid course ID."""
        response = self._make_request("invalid-course-id")
        self._assert_invalid_course_response(response)

    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_csv_export_no_permission(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock
    ):
        """Test CSV export when user has no permissions."""
        course_staff_role_mock.return_value.has_user.return_value = False
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False

        response = self._make_request()
        self._assert_no_permission_response(response)

    def test_csv_export_unauthenticated_access(self):
        """Test CSV export when user is not authenticated."""
        self.user.is_authenticated = False
        response = self._make_request()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @export_csv_task_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_csv_export_task_delay_called_correctly(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_csv_task_mock: MagicMock,
    ):
        """Test that the Celery task is called with delay method and correct parameters."""
        course_staff_role_mock.return_value.has_user.return_value = True
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        mock_task_result = MagicMock()
        export_csv_task_mock.delay.return_value = mock_task_result

        response = self._make_request()

        # Verify task was called with delay (asynchronous)
        export_csv_task_mock.delay.assert_called_once_with(self.course_id)
        # Verify task was not called synchronously
        export_csv_task_mock.assert_not_called()
        self._assert_success_response(response)

    @export_csv_task_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_csv_export_with_different_course_id_format(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_csv_task_mock: MagicMock,
    ):
        """Test CSV export with different course ID format."""
        different_course_id = "course-v1:MIT+6.00x+2023_T1"
        course_staff_role_mock.return_value.has_user.return_value = True
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        export_csv_task_mock.delay.return_value = MagicMock()

        response = self._make_request(different_course_id)

        self._assert_success_response(response)
        export_csv_task_mock.delay.assert_called_once_with(different_course_id)

    @export_csv_task_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_csv_export_response_structure(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_csv_task_mock: MagicMock,
    ):
        """Test that CSV export response has correct structure."""
        course_staff_role_mock.return_value.has_user.return_value = True
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        export_csv_task_mock.delay.return_value = MagicMock()

        response = self._make_request()

        # Verify response structure
        self.assertIn("success", response.data)
        self.assertIn("message", response.data)
        self.assertIsInstance(response.data["success"], bool)
        self.assertIsInstance(response.data["message"], str)
        self.assertTrue(response.data["success"])

    @export_csv_task_patch
    @course_instructor_role_patch
    @course_staff_role_patch
    @course_data_researcher_role_patch
    def test_csv_export_permission_check_order(
        self,
        course_staff_role_mock: MagicMock,
        course_instructor_role_mock: MagicMock,
        course_data_researcher_role_mock: MagicMock,
        export_csv_task_mock: MagicMock,
    ):
        """Test that permission checks are performed in correct order."""
        # Setup: user has staff role but not instructor role
        course_staff_role_mock.return_value.has_user.return_value = True
        course_instructor_role_mock.return_value.has_user.return_value = False
        course_data_researcher_role_mock.return_value.has_user.return_value = False
        export_csv_task_mock.delay.return_value = MagicMock()

        response = self._make_request()

        # Verify both role checks were performed
        course_staff_role_mock.assert_called_once_with(self.course_key)
        course_instructor_role_mock.assert_called_once_with(self.course_key)

        # Verify the staff role check
        course_staff_role_mock.return_value.has_user.assert_called_once_with(self.user)

        self._assert_success_response(response)
