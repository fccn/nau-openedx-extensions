"""
Unit tests for the profile completion API.
"""

from unittest.mock import MagicMock, patch

from django.test.utils import override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from nau_openedx_extensions.profile_completion.views import INVALID_COURSE_MESSAGE, ProfileCompletionAPIView

VIEWS_MODULE_PATH = "nau_openedx_extensions.profile_completion.views"
ACCOUNT_URL = "http://apps.example.com/account/"


@patch(f"{VIEWS_MODULE_PATH}.CourseInstructorRole")
@patch(f"{VIEWS_MODULE_PATH}.CourseStaffRole")
@patch(f"{VIEWS_MODULE_PATH}.missing_profile_fields")
class ProfileCompletionAPIViewTest(APITestCase):
    """Test cases for ProfileCompletionAPIView."""

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.course_id = "course-v1:NAU+Demo+DemoCourse"
        self.view = ProfileCompletionAPIView.as_view()

        self.user = MagicMock()
        self.user.is_staff = False
        self.user.is_authenticated = True

    def _get(self, course_id=None, user=None):
        course_id = course_id or self.course_id
        request = self.factory.get(f"nau-openedx-extensions/profile-completion/courses/{course_id}/")
        force_authenticate(request, user=user or self.user)
        return self.view(request, course_id=course_id)

    @staticmethod
    def _not_course_staff(*role_mocks):
        for role_mock in role_mocks:
            role_mock.return_value.has_user.return_value = False

    @override_settings(ACCOUNT_MICROFRONTEND_URL=ACCOUNT_URL)
    def test_missing_fields_come_with_labels_and_the_account_link(self, missing_mock, staff_mock, instructor_mock):
        self._not_course_staff(staff_mock, instructor_mock)
        missing_mock.return_value = ["nif", "year_of_birth"]

        response = self._get()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["missing"], [
            {"name": "nif", "label": "NIF"},
            {"name": "year_of_birth", "label": "Year of birth"},
        ])
        self.assertEqual(response.data["account_url"], f"{ACCOUNT_URL}?missing=nif%2Cyear_of_birth")

    @override_settings(ACCOUNT_MICROFRONTEND_URL=ACCOUNT_URL)
    def test_nothing_missing(self, missing_mock, staff_mock, instructor_mock):
        self._not_course_staff(staff_mock, instructor_mock)
        missing_mock.return_value = []

        response = self._get()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"missing": [], "account_url": None})

    @override_settings(ACCOUNT_MICROFRONTEND_URL="")
    def test_no_account_link_without_the_account_mfe(self, missing_mock, staff_mock, instructor_mock):
        self._not_course_staff(staff_mock, instructor_mock)
        missing_mock.return_value = ["nif"]

        response = self._get()

        self.assertEqual(response.data["missing"], [{"name": "nif", "label": "NIF"}])
        self.assertIsNone(response.data["account_url"])

    def test_global_staff_are_never_missing_fields(self, missing_mock, staff_mock, instructor_mock):
        self._not_course_staff(staff_mock, instructor_mock)
        self.user.is_staff = True

        response = self._get()

        self.assertEqual(response.data, {"missing": [], "account_url": None})
        missing_mock.assert_not_called()

    def test_course_team_is_never_missing_fields(self, missing_mock, staff_mock, instructor_mock):
        self._not_course_staff(instructor_mock)
        staff_mock.return_value.has_user.return_value = True

        response = self._get()

        self.assertEqual(response.data, {"missing": [], "account_url": None})
        missing_mock.assert_not_called()

    def test_invalid_course_key(self, missing_mock, *_):
        response = self._get(course_id="not-a-course")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {"course_id": INVALID_COURSE_MESSAGE})
        missing_mock.assert_not_called()

    def test_anonymous_user_is_rejected(self, missing_mock, *_):
        request = self.factory.get(f"nau-openedx-extensions/profile-completion/courses/{self.course_id}/")

        response = self.view(request, course_id=self.course_id)

        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        missing_mock.assert_not_called()
