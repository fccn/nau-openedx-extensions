# -*- coding: utf-8 -*-
"""
Test cases for the per-course Student Profile Info CSV column segmentation
(fccn/nau-technical#797).

Covers the two configuration layers (Django allowlist + course advanced
setting), the ``upload_students_csv`` task wrapper, the installation of the
wrapper in the real edx-platform modules, and an end-to-end run of the real
report generator against a course fixture.
"""
import csv
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from nau_openedx_extensions.utils.instructor_analytics import (
    _COURSE_SETTING_KEY,
    _DJANGO_ALLOWLIST_SETTING,
    get_nau_additional_course_features,
    install_upload_students_csv_wrapper,
    upload_students_csv_factory,
)

from common.djangoapps.student.tests.factories import (  # isort:skip pylint: disable=import-error,wrong-import-order
    CourseEnrollmentFactory,
    UserFactory,
)
from xmodule.modulestore.tests.django_utils import \
    SharedModuleStoreTestCase  # isort:skip pylint: disable=import-error,wrong-import-order
from xmodule.modulestore.tests.factories import \
    CourseFactory  # isort:skip pylint: disable=import-error,wrong-import-order

_ALL_EXTRA_FEATURES = ["nau_nif", "nau_user_extended_model_cc_nic"]
_GET_SETTINGS_PATCH = "nau_openedx_extensions.utils.instructor_analytics.get_other_course_settings"
_COURSE_KEY = "course-v1:FCT+P797+2026_T1"


def _course_settings(extra_features):
    """Return the get_other_course_settings shape for the given setting value."""
    value = {}
    if extra_features is not None:
        value[_COURSE_SETTING_KEY] = extra_features
    return {"value": value}


class GetNauAdditionalCourseFeaturesTest(TestCase):
    """
    Unit tests for get_nau_additional_course_features: the course advanced
    setting selects fields, the Django allowlist limits which are permitted.
    """

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_no_course_setting_returns_empty(self, get_settings_mock):
        """Without the course advanced setting, no extra fields are returned."""
        get_settings_mock.return_value = _course_settings(None)

        self.assertEqual(get_nau_additional_course_features(_COURSE_KEY), [])

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_empty_course_setting_returns_empty(self, get_settings_mock):
        """An empty list in the course advanced setting yields no extra fields."""
        get_settings_mock.return_value = _course_settings([])

        self.assertEqual(get_nau_additional_course_features(_COURSE_KEY), [])

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_non_list_course_setting_is_ignored(self, get_settings_mock):
        """A malformed (non-list) course setting is ignored with a warning."""
        get_settings_mock.return_value = _course_settings("nau_nif")

        with self.assertLogs("nau_openedx_extensions.utils.instructor_analytics", level="WARNING"):
            self.assertEqual(get_nau_additional_course_features(_COURSE_KEY), [])

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_fields_not_in_allowlist_are_skipped(self, get_settings_mock):
        """Only allowlisted fields pass; unlisted ones are skipped with a warning."""
        get_settings_mock.return_value = _course_settings(["nau_nif", "password", "nau_user_extended_model_cc_nic"])

        with self.assertLogs("nau_openedx_extensions.utils.instructor_analytics", level="WARNING") as logs:
            features = get_nau_additional_course_features(_COURSE_KEY)

        self.assertEqual(features, ["nau_nif", "nau_user_extended_model_cc_nic"])
        self.assertTrue(any("password" in line for line in logs.output))

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: []})
    def test_empty_allowlist_denies_everything(self, get_settings_mock):
        """Deny by default: with an empty allowlist no course can add fields."""
        get_settings_mock.return_value = _course_settings(["nau_nif"])

        with self.assertLogs("nau_openedx_extensions.utils.instructor_analytics", level="WARNING"):
            self.assertEqual(get_nau_additional_course_features(_COURSE_KEY), [])

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_duplicates_are_removed_preserving_order(self, get_settings_mock):
        """Duplicate entries in the course setting are deduplicated, order kept."""
        get_settings_mock.return_value = _course_settings(
            ["nau_user_extended_model_cc_nic", "nau_nif", "nau_user_extended_model_cc_nic"]
        )

        self.assertEqual(
            get_nau_additional_course_features(_COURSE_KEY),
            ["nau_user_extended_model_cc_nic", "nau_nif"],
        )

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(
        **{
            _DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES,
            "PROFILE_INFORMATION_REPORT_PRIVATE_FIELDS": ["nau_nif"],
        }
    )
    def test_private_fields_cannot_be_enabled_per_course(self, get_settings_mock):
        """A field marked private site-wide is skipped even when allowlisted."""
        get_settings_mock.return_value = _course_settings(["nau_nif", "nau_user_extended_model_cc_nic"])

        with self.assertLogs("nau_openedx_extensions.utils.instructor_analytics", level="WARNING") as logs:
            features = get_nau_additional_course_features(_COURSE_KEY)

        self.assertEqual(features, ["nau_user_extended_model_cc_nic"])
        self.assertTrue(any("private" in line for line in logs.output))


def _recording_task(calls, return_value="task-result"):
    """
    Return a plain function with the upload_students_csv signature that records
    its calls. A closure (not a Mock) so functools.wraps and the idempotence
    attribute behave exactly as with the real task function.
    """

    def upload_students_csv(_xblock_instance_args, _entry_id, course_id, task_input, action_name):
        calls.append((course_id, task_input, action_name))
        return return_value

    return upload_students_csv


class UploadStudentsCsvWrapperTest(TestCase):
    """Unit tests for the upload_students_csv task wrapper."""

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_extra_fields_are_appended_to_task_features(self, get_settings_mock):
        """Course-selected fields are appended to the task's feature list."""
        get_settings_mock.return_value = _course_settings(["nau_nif"])
        calls = []
        wrapped = upload_students_csv_factory(_recording_task(calls))

        result = wrapped(None, None, _COURSE_KEY, {"features": ["id", "username"]}, "generated")

        self.assertEqual(result, "task-result")
        self.assertEqual(calls[0][1]["features"], ["id", "username", "nau_nif"])

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_fields_already_present_are_not_duplicated(self, get_settings_mock):
        """A course-selected field already in the feature list is not repeated."""
        get_settings_mock.return_value = _course_settings(["nau_nif"])
        calls = []
        wrapped = upload_students_csv_factory(_recording_task(calls))

        wrapped(None, None, _COURSE_KEY, {"features": ["id", "nau_nif"]}, "generated")

        self.assertEqual(calls[0][1]["features"], ["id", "nau_nif"])

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_passthrough_when_course_has_no_extra_fields(self, get_settings_mock):
        """Without the course setting, the task input is passed through untouched."""
        get_settings_mock.return_value = _course_settings(None)
        calls = []
        wrapped = upload_students_csv_factory(_recording_task(calls))
        task_input = {"features": ["id", "username"]}

        wrapped(None, None, _COURSE_KEY, task_input, "generated")

        self.assertIs(calls[0][1], task_input)

    @patch(_GET_SETTINGS_PATCH)
    @override_settings(**{_DJANGO_ALLOWLIST_SETTING: _ALL_EXTRA_FEATURES})
    def test_original_task_input_is_not_mutated(self, get_settings_mock):
        """The wrapper builds a new task_input; the caller's dict is unchanged."""
        get_settings_mock.return_value = _course_settings(["nau_nif"])
        calls = []
        wrapped = upload_students_csv_factory(_recording_task(calls))
        task_input = {"features": ["id"]}

        wrapped(None, None, _COURSE_KEY, task_input, "generated")

        self.assertEqual(task_input, {"features": ["id"]})
        self.assertEqual(calls[0][1]["features"], ["id", "nau_nif"])

    def test_wrapper_is_marked_for_idempotence(self):
        """The wrapper carries the marker attribute that prevents double wrapping."""
        wrapped = upload_students_csv_factory(_recording_task([]))

        self.assertTrue(wrapped._nau_additional_course_features)  # pylint: disable=protected-access


class InstallTest(TestCase):
    """The wrapper must be installed in both real modules, exactly once."""

    def test_both_write_paths_are_wrapped(self):
        """AppConfig.ready() wrapped upload_students_csv where it is defined and where it is imported."""
        from lms.djangoapps.instructor_task import tasks  # pylint: disable=import-error,import-outside-toplevel
        from lms.djangoapps.instructor_task.tasks_helper import \
            enrollments  # pylint: disable=import-error,import-outside-toplevel

        for module in (enrollments, tasks):
            self.assertTrue(
                getattr(module.upload_students_csv, "_nau_additional_course_features", False),
                f"upload_students_csv is not wrapped in {module.__name__}",
            )

    def test_install_is_idempotent(self):
        """Running the installer again must not wrap the wrapper."""
        from lms.djangoapps.instructor_task import tasks  # pylint: disable=import-error,import-outside-toplevel
        from lms.djangoapps.instructor_task.tasks_helper import \
            enrollments  # pylint: disable=import-error,import-outside-toplevel

        before = (enrollments.upload_students_csv, tasks.upload_students_csv)
        install_upload_students_csv_wrapper()

        self.assertEqual(before, (enrollments.upload_students_csv, tasks.upload_students_csv))


CURRENT_TASK_PATCH = "lms.djangoapps.instructor_task.tasks_helper.runner._get_current_task"


class RealStudentProfileReportTest(SharedModuleStoreTestCase):
    """
    End to end: a real course fixture with the advanced setting configured, the
    real (wrapped) upload_students_csv task, and the stored CSV carrying the
    extra column. This detects upstream refactors of the task or of the course
    settings plumbing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = CourseFactory.create(
            org="FCT",
            number="P797",
            run="2026_T1",
            other_course_settings={_COURSE_SETTING_KEY: ["nau_nif", "field_not_allowed"]},
        )

    def setUp(self):
        super().setUp()
        self.tmpdir = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.tmpdir.cleanup)
        self.overrides = override_settings(
            GRADES_DOWNLOAD={
                "STORAGE_TYPE": "localfs",
                "BUCKET": "test-grades",
                "ROOT_PATH": self.tmpdir.name,
            },
            **{_DJANGO_ALLOWLIST_SETTING: ["nau_nif"]},
        )
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        self.learner = UserFactory(username="p797_learner")
        CourseEnrollmentFactory(user=self.learner, course_id=self.course.id, is_active=True)

    def _stored_rows(self):
        """Return the parsed rows of the single stored report."""
        for dirpath, _dirnames, filenames in os.walk(self.tmpdir.name):
            for name in filenames:
                with open(os.path.join(dirpath, name), encoding="utf-8") as stored:
                    return list(csv.reader(stored))
        self.fail("no report was stored")
        return []  # pragma: no cover

    def test_report_carries_the_course_selected_column(self):
        """The stored CSV gains the allowlisted extra column, and only that one."""
        from lms.djangoapps.instructor_task.tasks_helper import \
            enrollments  # pylint: disable=import-error,import-outside-toplevel

        with patch(CURRENT_TASK_PATCH):
            enrollments.upload_students_csv(
                None, None, self.course.id, {"features": ["id", "username", "email"]}, "generated"
            )

        rows = self._stored_rows()
        self.assertEqual(rows[0], ["id", "username", "email", "nau_nif"])
        self.assertNotIn("field_not_allowed", rows[0])
        self.assertEqual(
            rows[1][:3],
            [str(self.learner.id), self.learner.username, self.learner.email],
        )
