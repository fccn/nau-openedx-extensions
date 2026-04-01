"""
Unit tests for course_filters.sync module.
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.course_filters.models import NauCourseFilter
from nau_openedx_extensions.course_filters.sync import (
    get_known_filter_keys,
    sync_course_filters_for_course,
)

SYNC_PATH = "nau_openedx_extensions.course_filters.sync"

COURSE_ID = "course-v1:Demo+DemoX+Demo_Course"


class GetKnownFilterKeysTest(TestCase):
    """Tests for get_known_filter_keys()."""

    def test_returns_defaults_when_setting_absent(self):
        keys = get_known_filter_keys()
        self.assertIn("filter_enrollment_by_domain_list", keys)
        self.assertIn("filter_enrollment_require_nif", keys)
        self.assertIn("certificate_require_portuguese_citizen_card", keys)

    @override_settings(NAU_COURSE_FILTER_KEYS=("custom_filter_a", "custom_filter_b"))
    def test_returns_custom_keys_from_settings(self):
        keys = get_known_filter_keys()
        self.assertEqual(keys, ("custom_filter_a", "custom_filter_b"))


class SyncCourseFiltersForCourseTest(TestCase):
    """Tests for sync_course_filters_for_course()."""

    def setUp(self):
        self.course_key = CourseKey.from_string(COURSE_ID)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_no_filters_active_creates_no_rows(self, mock_get_settings):
        """
        When other_course_settings has no known filter keys, no rows are created.
        """
        mock_get_settings.return_value = {"value": {}}

        result = sync_course_filters_for_course(self.course_key)

        self.assertEqual(NauCourseFilter.objects.filter(course_id=COURSE_ID).count(), 0)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["deleted"], 0)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_multiple_active_filters_creates_rows(self, mock_get_settings):
        """
        When multiple known filter keys have truthy values, rows are created for each.
        """
        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_require_nif": True,
                "certificate_require_portuguese_citizen_card": True,
            }
        }

        result = sync_course_filters_for_course(self.course_key)

        filters = NauCourseFilter.objects.filter(course_id=COURSE_ID)
        filter_types = set(filters.values_list("filter_type", flat=True))
        self.assertIn("filter_enrollment_require_nif", filter_types)
        self.assertIn("certificate_require_portuguese_citizen_card", filter_types)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["deleted"], 0)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_filter_with_domain_list_creates_row(self, mock_get_settings):
        """
        A non-empty list value for filter_enrollment_by_domain_list is truthy and creates a row.
        """
        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_by_domain_list": ["example.com", "test.org"],
            }
        }

        result = sync_course_filters_for_course(self.course_key)

        self.assertTrue(
            NauCourseFilter.objects.filter(
                course_id=COURSE_ID, filter_type="filter_enrollment_by_domain_list"
            ).exists()
        )
        self.assertEqual(result["created"], 1)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_filter_removal_deletes_rows(self, mock_get_settings):
        """
        Rows for filters that are no longer active in other_course_settings are deleted.
        """
        NauCourseFilter.objects.create(
            course_id=COURSE_ID, filter_type="filter_enrollment_require_nif"
        )
        NauCourseFilter.objects.create(
            course_id=COURSE_ID, filter_type="certificate_require_portuguese_citizen_card"
        )

        mock_get_settings.return_value = {"value": {}}

        result = sync_course_filters_for_course(self.course_key)

        self.assertEqual(NauCourseFilter.objects.filter(course_id=COURSE_ID).count(), 0)
        self.assertEqual(result["deleted"], 2)
        self.assertEqual(result["created"], 0)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_partial_update_adds_and_removes(self, mock_get_settings):
        """
        When some filters are added and some removed in the same publish, both operations happen.
        """
        NauCourseFilter.objects.create(
            course_id=COURSE_ID, filter_type="filter_enrollment_require_nif"
        )

        mock_get_settings.return_value = {
            "value": {
                "certificate_require_portuguese_citizen_card": True,
            }
        }

        result = sync_course_filters_for_course(self.course_key)

        filter_types = set(
            NauCourseFilter.objects.filter(course_id=COURSE_ID).values_list("filter_type", flat=True)
        )
        self.assertIn("certificate_require_portuguese_citizen_card", filter_types)
        self.assertNotIn("filter_enrollment_require_nif", filter_types)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["deleted"], 1)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_unchanged_filters_are_counted(self, mock_get_settings):
        """
        Filters that are active both before and after the sync are reported as unchanged.
        """
        NauCourseFilter.objects.create(
            course_id=COURSE_ID, filter_type="filter_enrollment_require_nif"
        )

        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_require_nif": True,
            }
        }

        result = sync_course_filters_for_course(self.course_key)

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(result["unchanged"], 1)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_falsy_filter_value_creates_no_row(self, mock_get_settings):
        """
        Filter keys with falsy values (False, empty list, empty string) do not create rows.
        """
        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_require_nif": False,
                "filter_enrollment_by_domain_list": [],
                "certificate_require_portuguese_citizen_card": "",
            }
        }

        result = sync_course_filters_for_course(self.course_key)

        self.assertEqual(NauCourseFilter.objects.filter(course_id=COURSE_ID).count(), 0)
        self.assertEqual(result["created"], 0)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_exception_in_get_settings_does_not_raise(self, mock_get_settings):
        """
        If get_other_course_settings raises, sync_course_filters_for_course catches it and returns
        without raising, so the course_published signal handler is never blocked.
        """
        mock_get_settings.side_effect = Exception("MongoDB connection failed")

        result = sync_course_filters_for_course(self.course_key)

        self.assertEqual(result, {"created": 0, "deleted": 0, "unchanged": 0})
        self.assertEqual(NauCourseFilter.objects.filter(course_id=COURSE_ID).count(), 0)

    @patch(f"{SYNC_PATH}.get_other_course_settings")
    def test_idempotent_on_repeated_calls(self, mock_get_settings):
        """
        Calling sync twice with the same settings produces no duplicate rows.
        """
        mock_get_settings.return_value = {
            "value": {
                "filter_enrollment_require_nif": True,
            }
        }

        sync_course_filters_for_course(self.course_key)
        result = sync_course_filters_for_course(self.course_key)

        self.assertEqual(NauCourseFilter.objects.filter(course_id=COURSE_ID).count(), 1)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["unchanged"], 1)
