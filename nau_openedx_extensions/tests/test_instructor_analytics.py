# -*- coding: utf-8 -*-
"""
Test cases for instructor analytics utilities.

This module tests the monkey-patching of ``get_student_features_with_custom``
which appends additional student profile fields when the course advanced setting
``nau_additional_features_on_instructor_analytics_student_profile_info`` is configured,
subject to the global Django allowlist
``NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO``.
"""
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from nau_openedx_extensions.utils.instructor_analytics import (
    _COURSE_SETTING_KEY,
    _DJANGO_ALLOWLIST_SETTING,
    get_student_features_with_custom_factory,
)

_BASE_FEATURES = ("id", "username", "name", "email", "year_of_birth")
_ALL_EXTRA_FEATURES = ["nau_nif", "nau_user_extended_model_cc_nic"]


def _make_course_key():
    """Return a simple mock that behaves like a CourseKey."""
    return Mock()


def _make_original(features=_BASE_FEATURES):
    """Return a mock original function that always returns *features*."""
    return Mock(return_value=features)


def _make_course_settings(extra_features=None):
    """
    Return a mocked return value for get_other_course_settings.

    Args:
        extra_features: list of extra feature names, or None for no setting present.
    """
    value = {}
    if extra_features is not None:
        value[_COURSE_SETTING_KEY] = extra_features
    return {"value": value}


class TestGetStudentFeaturesWithCustomFactory(TestCase):
    """
    Unit tests for get_student_features_with_custom_factory.

    Two layers of configuration are tested:

    1. The Django allowlist (``NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO``)
       defines every field name that is ever permitted site-wide.
    2. The per-course advanced setting (``nau_additional_features_on_instructor_analytics_student_profile_info``)
       selects which of those allowed fields are active for a given course.
    """

    # ------------------------------------------------------------------
    # Original function delegation
    # ------------------------------------------------------------------

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_original_function_always_called(self, mock_get_other_course_settings):
        """The original get_student_features_with_custom is always invoked regardless of settings."""
        mock_get_other_course_settings.return_value = _make_course_settings(["nau_nif"])
        original = _make_original()
        wrapper = get_student_features_with_custom_factory(original)
        course_key = _make_course_key()

        wrapper(course_key)

        original.assert_called_once_with(course_key)

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_get_other_course_settings_called_with_course_key(self, mock_get_other_course_settings):
        """get_other_course_settings is called with the same course_key passed to the wrapper."""
        mock_get_other_course_settings.return_value = _make_course_settings()
        original = _make_original()
        wrapper = get_student_features_with_custom_factory(original)
        course_key = _make_course_key()

        wrapper(course_key)

        mock_get_other_course_settings.assert_called_once_with(course_key)

    # ------------------------------------------------------------------
    # No course-level setting present
    # ------------------------------------------------------------------

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_no_course_setting_returns_original_features(self, mock_get_other_course_settings):
        """When the course setting key is absent, the original features are returned unchanged."""
        mock_get_other_course_settings.return_value = _make_course_settings()
        original = _make_original()
        wrapper = get_student_features_with_custom_factory(original)

        result = wrapper(_make_course_key())

        self.assertEqual(result, _BASE_FEATURES)

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_empty_other_course_settings_returns_original_features(self, mock_get_other_course_settings):
        """An empty dict from get_other_course_settings does not break the wrapper."""
        mock_get_other_course_settings.return_value = {}

        result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertEqual(result, _BASE_FEATURES)

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_empty_course_setting_list_returns_original_features(self, mock_get_other_course_settings):
        """An empty list in the course setting returns original features unchanged."""
        mock_get_other_course_settings.return_value = _make_course_settings([])

        result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertEqual(result, _BASE_FEATURES)

    # ------------------------------------------------------------------
    # Happy path: fields appended correctly
    # ------------------------------------------------------------------

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_allowlisted_course_fields_are_appended(self, mock_get_other_course_settings):
        """All course-requested fields that are in the allowlist are appended in order."""
        mock_get_other_course_settings.return_value = _make_course_settings(
            ["nau_nif", "nau_user_extended_model_cc_nic"]
        )

        result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertEqual(result, _BASE_FEATURES + ("nau_nif", "nau_user_extended_model_cc_nic"))

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_field_order_is_preserved(self, mock_get_other_course_settings):
        """Extra fields are appended in the order they appear in the course setting."""
        mock_get_other_course_settings.return_value = _make_course_settings(
            ["nau_user_extended_model_cc_nic", "nau_nif"]
        )

        result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertEqual(
            result, _BASE_FEATURES + ("nau_user_extended_model_cc_nic", "nau_nif")
        )

    # ------------------------------------------------------------------
    # Duplicate field prevention
    # ------------------------------------------------------------------

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: ["name", "nau_nif"]})
    def test_field_already_in_base_not_duplicated(self, mock_get_other_course_settings):
        """A field that is already in the original result is not appended again."""
        mock_get_other_course_settings.return_value = _make_course_settings(
            ["name", "nau_nif"]  # "name" already in _BASE_FEATURES
        )

        result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertEqual(result.count("name"), 1)
        self.assertIn("nau_nif", result)

    # ------------------------------------------------------------------
    # Allowlist filtering
    # ------------------------------------------------------------------

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: ["nau_nif"]})
    def test_field_not_in_allowlist_is_skipped_with_warning(self, mock_get_other_course_settings):
        """A course-requested field absent from the allowlist is skipped and a WARNING is emitted."""
        mock_get_other_course_settings.return_value = _make_course_settings(
            ["nau_nif", "nau_user_extended_model_cc_nic"]  # cc_nic not in allowlist
        )

        with self.assertLogs('nau_openedx_extensions.utils.instructor_analytics', level='WARNING') as log:
            result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertIn("nau_nif", result)
        self.assertNotIn("nau_user_extended_model_cc_nic", result)
        self.assertTrue(any("nau_user_extended_model_cc_nic" in msg for msg in log.output))

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: []})
    def test_empty_allowlist_blocks_all_fields_with_warnings(self, mock_get_other_course_settings):
        """An empty allowlist blocks every course-level field and warns for each one."""
        mock_get_other_course_settings.return_value = _make_course_settings(
            ["nau_nif", "nau_user_extended_model_cc_nic"]
        )

        with self.assertLogs('nau_openedx_extensions.utils.instructor_analytics', level='WARNING') as log:
            result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertEqual(result, _BASE_FEATURES)
        # One warning per blocked field
        warning_messages = [m for m in log.output if 'WARNING' in m]
        self.assertEqual(len(warning_messages), 2)

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_unknown_field_in_course_setting_skipped_with_warning(self, mock_get_other_course_settings):
        """A field in the course setting that is not in the allowlist is skipped with a warning."""
        mock_get_other_course_settings.return_value = _make_course_settings(
            ["nau_nif", "unknown_field"]
        )

        with self.assertLogs('nau_openedx_extensions.utils.instructor_analytics', level='WARNING') as log:
            result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertIn("nau_nif", result)
        self.assertNotIn("unknown_field", result)
        self.assertTrue(any("unknown_field" in msg for msg in log.output))

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    def test_absent_django_allowlist_setting_blocks_all_fields(self, mock_get_other_course_settings):
        """When the Django allowlist setting is missing entirely, no extra fields are appended."""
        mock_get_other_course_settings.return_value = _make_course_settings(["nau_nif"])

        with self.assertLogs('nau_openedx_extensions.utils.instructor_analytics', level='WARNING'):
            result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertEqual(result, _BASE_FEATURES)

    # ------------------------------------------------------------------
    # Malformed course setting value
    # ------------------------------------------------------------------

    @patch('nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings')
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_non_list_course_setting_is_ignored_with_warning(self, mock_get_other_course_settings):
        """A non-list value for the course setting is ignored and a WARNING is logged."""
        mock_get_other_course_settings.return_value = _make_course_settings("bad-value")

        with self.assertLogs('nau_openedx_extensions.utils.instructor_analytics', level='WARNING') as log:
            result = get_student_features_with_custom_factory(_make_original())(_make_course_key())

        self.assertEqual(result, _BASE_FEATURES)
        self.assertTrue(any("not a list" in msg for msg in log.output))
