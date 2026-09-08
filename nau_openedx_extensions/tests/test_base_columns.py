"""
Conformance tests for the report base-columns wrapper (ADR 0001).

These tests are mandatory, not optional. The wrapper rebinds functions inside
edx-platform modules we do not control; if an upgrade renames those modules or
changes how they import the upload functions, the rebinding silently does
nothing and reports keep generating without the base columns. This suite makes
that breakage surface during the upgrade instead of when the partner reports
missing data.
"""

import csv
import os
from datetime import datetime, timezone
from io import StringIO
from tempfile import TemporaryDirectory, TemporaryFile
from unittest.mock import patch

from common.djangoapps.student.models import anonymous_id_for_user  # pylint: disable=import-error
from common.djangoapps.student.tests.factories import (  # pylint: disable=import-error
    CourseEnrollmentFactory,
    UserFactory,
)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import OutputWrapper
from django.test import TestCase
from django.test.utils import override_settings
from lms.djangoapps.certificates.tests.factories import GeneratedCertificateFactory  # pylint: disable=import-error
from lms.djangoapps.instructor_task.tasks_helper import enrollments, grades, misc, utils  # pylint: disable=import-error
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase  # pylint: disable=import-error
from xmodule.modulestore.tests.factories import CourseFactory  # pylint: disable=import-error

from nau_openedx_extensions.certificate_export.management.commands.export_course_certificates import \
    Command as ExportCertificatesCommand
from nau_openedx_extensions.reports import base_columns

COURSE_KEY = CourseKey.from_string("course-v1:FCT+CTC101x+2020_T2")
BASE_VALUES = ["FCT", "course-v1:FCT+CTC101x+2020_T2", "2020_T2"]
CURRENT_TASK_PATCH = "lms.djangoapps.instructor_task.tasks_helper.runner._get_current_task"

User = get_user_model()


def _stored_reports(root):
    """
    Return a mapping of stored report file name to its parsed CSV rows.
    """
    reports = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            with open(os.path.join(dirpath, name), encoding="utf-8") as stored:
                reports[name] = list(csv.reader(stored))
    return reports


def _recording_upload(calls, return_value="report_name.csv"):
    """
    Return a plain function with the upload helpers' signature that records
    its calls. A real function (not a Mock) is required: the wrappers use
    ``functools.wraps`` and check a marker attribute with ``getattr``, both of
    which Mock's auto-created attributes break.
    """

    def upload(rows_or_file, csv_name, course_id, timestamp, *args, **kwargs):
        """Record the call and return a canned report name."""
        calls.append((rows_or_file, csv_name, course_id, timestamp, args, kwargs))
        return return_value

    return upload


class WrapperBehaviorTest(TestCase):
    """
    Unit tests for the row/file wrappers and the column transformation.
    """

    def test_setting_defaults_off(self):
        """
        The plugin setting must default to off: shipping the wrapper must not
        change any report until the deployment explicitly enables it.
        """
        self.assertFalse(settings.NAU_REPORTS_ENABLE_BASE_COLUMNS)

    def test_wrapper_is_passthrough_when_disabled(self):
        """
        With the setting off, the wrapped upload receives the rows unchanged
        and its return value is passed through.
        """
        calls = []
        upload = _recording_upload(calls)
        wrapped = base_columns._wrap_rows(upload)  # pylint: disable=protected-access
        self.assertIsNot(wrapped, upload)
        rows = [["Username", "Grade"], ["learner1", "0.83"]]

        result = wrapped(rows, "grade_report", COURSE_KEY, datetime.now(timezone.utc))

        self.assertEqual(result, "report_name.csv")
        self.assertEqual(calls[0][0], rows)

    @override_settings(NAU_REPORTS_ENABLE_BASE_COLUMNS=True)
    def test_learner_grain_gets_all_base_columns(self):
        """
        A report with a username column is learner grain: it gets org_id,
        course_id, course_run and anonymous_user_id first, and the anonymous
        id must match anonymous_id_for_user for that learner and course.
        """
        learner_1 = User.objects.create(username="learner1", email="l1@example.com")
        learner_2 = User.objects.create(username="learner2", email="l2@example.com")
        rows = [
            ["Username", "Grade"],
            ["learner1", "0.83"],
            ["learner2", "0.21"],
        ]

        new_rows = base_columns.add_base_columns(rows, COURSE_KEY)

        self.assertEqual(
            new_rows[0],
            ["org_id", "course_id", "course_run", "anonymous_user_id", "Username", "Grade"],
        )
        self.assertEqual(
            new_rows[1],
            BASE_VALUES + [anonymous_id_for_user(learner_1, COURSE_KEY), "learner1", "0.83"],
        )
        self.assertEqual(
            new_rows[2],
            BASE_VALUES + [anonymous_id_for_user(learner_2, COURSE_KEY), "learner2", "0.21"],
        )

    @override_settings(NAU_REPORTS_ENABLE_BASE_COLUMNS=True)
    def test_learner_column_aliases_of_the_four_target_reports(self):
        """
        The learner column is detected under the four spellings used by
        student_profile_info, grade_report, export_course_certificates and
        course_survey_results.
        """
        User.objects.create(username="learner1", email="l1@example.com")
        for header in ("username", "Username", "student username", "User Name"):
            with self.subTest(header=header):
                new_rows = base_columns.add_base_columns(
                    [[header, "Other"], ["learner1", "x"]], COURSE_KEY
                )
                self.assertEqual(new_rows[0][3], "anonymous_user_id")
                self.assertTrue(new_rows[1][3])  # anonymous id resolved

    @override_settings(NAU_REPORTS_ENABLE_BASE_COLUMNS=True)
    def test_course_grain_gets_course_columns_only(self):
        """
        A report without a learner column (e.g. cohort_results) is course
        grain: only the course columns are added and no learner column is
        introduced — omitted, never empty.
        """
        rows = [
            ["Cohort Name", "Exists in Cohort", "Learners Added"],
            ["cohort-a", "True", "12"],
        ]

        new_rows = base_columns.add_base_columns(rows, COURSE_KEY)

        self.assertEqual(
            new_rows[0],
            ["org_id", "course_id", "course_run", "Cohort Name", "Exists in Cohort", "Learners Added"],
        )
        self.assertEqual(new_rows[1], BASE_VALUES + ["cohort-a", "True", "12"])
        self.assertNotIn("anonymous_user_id", new_rows[0])

    @override_settings(NAU_REPORTS_ENABLE_BASE_COLUMNS=True)
    def test_profile_report_without_username_degrades_to_course_grain(self):
        """
        student_profile_info builds its header from the
        student_profile_download_fields site configuration, which REPLACES the
        defaults. If a deployment omits ``username`` there, the wrapper has no
        learner column to resolve and the report silently degrades to course
        grain. This test documents that behavior, as required by the ADR.
        """
        rows = [["id", "name", "email"], ["7", "Learner One", "l1@example.com"]]

        new_rows = base_columns.add_base_columns(rows, COURSE_KEY)

        self.assertNotIn("anonymous_user_id", new_rows[0])
        self.assertEqual(new_rows[0][:3], ["org_id", "course_id", "course_run"])

    @override_settings(NAU_REPORTS_ENABLE_BASE_COLUMNS=True)
    def test_unresolvable_username_gets_empty_anonymous_id(self):
        """
        A username that no longer resolves to a user (e.g. retired account)
        yields an empty anonymous_user_id cell rather than failing the report.
        """
        new_rows = base_columns.add_base_columns(
            [["Username", "Grade"], ["ghost-user", "0.5"]], COURSE_KEY
        )

        self.assertEqual(new_rows[1][3], "")

    @override_settings(NAU_REPORTS_ENABLE_BASE_COLUMNS=True)
    def test_file_wrapper_transforms_streamed_reports(self):
        """
        The file-based write path (large grade reports streamed to a temp
        file) gets the same transformation, applied line by line.
        """
        learner = User.objects.create(username="learner1", email="l1@example.com")
        source = TemporaryFile("r+", newline="", encoding="utf-8")
        csv.writer(source).writerows(
            [["Username", "Grade"], ["learner1", "0.83"]]
        )
        source.seek(0)
        calls = []
        upload = _recording_upload(calls, return_value="grade_report.csv")
        wrapped = base_columns._wrap_file(upload)  # pylint: disable=protected-access
        self.assertIsNot(wrapped, upload)

        wrapped(source, "grade_report", COURSE_KEY, datetime.now(timezone.utc))

        uploaded_file = calls[0][0]
        content = list(csv.reader(uploaded_file))
        self.assertEqual(
            content[0],
            ["org_id", "course_id", "course_run", "anonymous_user_id", "Username", "Grade"],
        )
        self.assertEqual(
            content[1],
            BASE_VALUES + [anonymous_id_for_user(learner, COURSE_KEY), "learner1", "0.83"],
        )


class InstallConformanceTest(TestCase):
    """
    Conformance tests for the rebinding itself: these are the tests that fail
    when an edx-platform upgrade breaks the write-path assumptions.
    """

    def test_all_write_paths_are_wrapped(self):
        """
        AppConfig.ready() must have rebound the upload helpers in utils and in
        the three report modules that import them into their own namespace.
        """
        base_columns.install()  # idempotent; ready() already ran it
        for module in (utils, enrollments, grades, misc):
            self.assertTrue(
                getattr(module.upload_csv_to_report_store, "_nau_base_columns", False),
                f"{module.__name__}.upload_csv_to_report_store is not wrapped",
            )
        for module in (utils, grades):
            self.assertTrue(
                getattr(module.upload_csv_file_to_report_store, "_nau_base_columns", False),
                f"{module.__name__}.upload_csv_file_to_report_store is not wrapped",
            )

    def test_install_is_idempotent(self):
        """
        Calling install() again must not wrap the wrappers.
        """
        base_columns.install()
        before = utils.upload_csv_to_report_store
        base_columns.install()
        self.assertIs(utils.upload_csv_to_report_store, before)

    def test_zip_write_path_is_not_wrapped(self):
        """
        upload_zip_to_report_store is deliberately left unwrapped: ZIP
        archives have no CSV header to extend.
        """
        self.assertFalse(
            getattr(utils.upload_zip_to_report_store, "_nau_base_columns", False)
        )
        self.assertFalse(
            getattr(misc.upload_zip_to_report_store, "_nau_base_columns", False)
        )


class EndToEndReportStoreTest(TestCase):
    """
    Generate reports through the real write path into a local report store and
    assert the stored CSVs, with the setting off (byte-identical behavior) and
    on (base columns present).
    """

    def setUp(self):
        super().setUp()
        self.tmpdir = TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.tmpdir.cleanup)
        self.grades_download = {
            "STORAGE_TYPE": "localfs",
            "BUCKET": "test-grades",
            "ROOT_PATH": self.tmpdir.name,
        }

    def _stored_csv_rows(self):
        """
        Return the parsed rows of the single CSV stored in the temp report
        store.
        """
        paths = []
        for dirpath, _dirnames, filenames in os.walk(self.tmpdir.name):
            paths.extend(os.path.join(dirpath, name) for name in filenames)
        self.assertEqual(len(paths), 1, f"expected exactly one stored report, got {paths}")
        with open(paths[0], encoding="utf-8") as stored:
            return list(csv.reader(stored))

    def test_report_is_unchanged_with_setting_off(self):
        """
        With the setting off (the default), the stored report is exactly what
        the platform produced — the wrapper must be a no-op.
        """
        rows = [["Username", "Grade"], ["learner1", "0.83"]]
        with override_settings(GRADES_DOWNLOAD=self.grades_download):
            enrollments.upload_csv_to_report_store(
                rows, "grade_report", COURSE_KEY, datetime.now(timezone.utc)
            )

        self.assertEqual(self._stored_csv_rows(), rows)

    def test_report_carries_base_columns_with_setting_on(self):
        """
        With the setting on, the stored report starts with the base columns
        and the resolved anonymous id.
        """
        learner = User.objects.create(username="learner1", email="l1@example.com")
        rows = [["Username", "Grade"], ["learner1", "0.83"]]
        with override_settings(
            GRADES_DOWNLOAD=self.grades_download, NAU_REPORTS_ENABLE_BASE_COLUMNS=True
        ):
            enrollments.upload_csv_to_report_store(
                rows, "grade_report", COURSE_KEY, datetime.now(timezone.utc)
            )

        stored = self._stored_csv_rows()
        self.assertEqual(
            stored[0],
            ["org_id", "course_id", "course_run", "anonymous_user_id", "Username", "Grade"],
        )
        self.assertEqual(
            stored[1],
            BASE_VALUES + [anonymous_id_for_user(learner, COURSE_KEY), "learner1", "0.83"],
        )

    def test_nau_custom_reports_go_through_the_wrapper(self):
        """
        The plugin's own reports (e.g. export_course_certificates) call the
        upload helpers through edxapp_wrapper.instructor_task, whose backend
        imports from utils. Wrapping utils must cover that path too.
        """
        # pylint: disable=import-outside-toplevel
        from nau_openedx_extensions.edxapp_wrapper.instructor_task import upload_csv_to_report_store

        learner = User.objects.create(username="learner1", email="l1@example.com")
        rows = [["student username", "certificate created date"], ["learner1", "2026-01-01"]]
        with override_settings(
            GRADES_DOWNLOAD=self.grades_download, NAU_REPORTS_ENABLE_BASE_COLUMNS=True
        ):
            upload_csv_to_report_store(
                rows, "export_course_certificates", COURSE_KEY, datetime.now(timezone.utc)
            )

        stored = self._stored_csv_rows()
        self.assertEqual(stored[0][3], "anonymous_user_id")
        self.assertEqual(stored[1][3], anonymous_id_for_user(learner, COURSE_KEY))


class RealGeneratorConformanceTest(TestCase):
    """
    Run the real platform report generators end to end (generator -> wrapped
    upload -> report store) and assert the stored CSVs conform to the base
    column contract. These generators live in edx-platform, so this is the part
    of the conformance suite that detects upstream refactors of the report
    code itself.
    """

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
            NAU_REPORTS_ENABLE_BASE_COLUMNS=True,
        )
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        self.learner = UserFactory(username="conf_learner1")
        CourseEnrollmentFactory(user=self.learner, course_id=COURSE_KEY, is_active=True)

    def _single_stored_report(self):
        """Return (name, rows) of the single report stored during the test."""
        reports = _stored_reports(self.tmpdir.name)
        self.assertEqual(len(reports), 1, f"expected one stored report, got {list(reports)}")
        return next(iter(reports.items()))

    def test_student_profile_info_is_learner_grain(self):
        """
        The real student_profile_info generator produces a learner-grain
        report: base columns first, anonymous id resolved per learner.
        """
        with patch(CURRENT_TASK_PATCH):
            enrollments.upload_students_csv(
                None, None, COURSE_KEY, {"features": ["id", "username", "email"]}, "generated"
            )

        name, rows = self._single_stored_report()
        self.assertIn("student_profile_info", name)
        self.assertEqual(
            rows[0],
            ["org_id", "course_id", "course_run", "anonymous_user_id", "id", "username", "email"],
        )
        self.assertEqual(
            rows[1],
            BASE_VALUES
            + [
                anonymous_id_for_user(self.learner, COURSE_KEY),
                str(self.learner.id),
                self.learner.username,
                self.learner.email,
            ],
        )

    def test_student_profile_info_without_username_degrades_to_course_grain(self):
        """
        The ADR hazard, through the real generator: if the deployment's
        student_profile_download_fields omits username, the report silently
        degrades to course grain (course columns only, no anonymous id).
        """
        with patch(CURRENT_TASK_PATCH):
            enrollments.upload_students_csv(
                None, None, COURSE_KEY, {"features": ["id", "email"]}, "generated"
            )

        _name, rows = self._single_stored_report()
        self.assertEqual(rows[0], ["org_id", "course_id", "course_run", "id", "email"])
        self.assertNotIn("anonymous_user_id", rows[0])

    def test_may_enroll_info_is_course_grain(self):
        """
        may_enroll_info carries only emails (no username column), so it gets
        the course columns and no learner column.
        """
        with patch(CURRENT_TASK_PATCH):
            enrollments.upload_may_enroll_csv(
                None, None, COURSE_KEY, {"features": ["email"]}, "generated"
            )

        name, rows = self._single_stored_report()
        self.assertIn("may_enroll_info", name)
        self.assertEqual(rows[0], ["org_id", "course_id", "course_run", "email"])


class CertificateExportConformanceTest(TestCase):
    """
    Run the NAU-owned export_course_certificates command end to end with the
    contract enabled: its own course_id column must be gone and the base
    columns (including the anonymous id resolved from "student username") must
    be present exactly once.
    """

    def test_certificates_report_conforms_without_duplicate_course_id(self):
        """
        The stored CSV starts with the base columns, carries course_id exactly
        once, and resolves the anonymous id from the certificate's user.
        """
        learner = UserFactory(username="cert_learner1")
        certificate = GeneratedCertificateFactory(
            user=learner, course_id=COURSE_KEY, verify_uuid="test-uuid-123"
        )
        command = ExportCertificatesCommand()
        command.stdout = OutputWrapper(StringIO())
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                GRADES_DOWNLOAD={
                    "STORAGE_TYPE": "localfs",
                    "BUCKET": "test-grades",
                    "ROOT_PATH": tmpdir,
                },
                NAU_REPORTS_ENABLE_BASE_COLUMNS=True,
                NAU_CERTIFICATE_DOWNLOAD_URL="https://certs.example.com",
            ):
                command.handle(course_ids=[str(COURSE_KEY)])
            reports = _stored_reports(tmpdir)

        self.assertEqual(len(reports), 1)
        rows = next(iter(reports.values()))
        self.assertEqual(
            rows[0],
            [
                "org_id",
                "course_id",
                "course_run",
                "anonymous_user_id",
                "student email",
                "student username",
                "student name",
                "certificate created date",
                "certificate verify_uuid",
                "certificate_web_link_url",
                "certificate_download_pdf_link",
            ],
        )
        self.assertEqual(rows[0].count("course_id"), 1)
        self.assertEqual(rows[1][:4], BASE_VALUES + [anonymous_id_for_user(learner, COURSE_KEY)])
        self.assertEqual(rows[1][5], learner.username)
        self.assertEqual(rows[1][8], certificate.verify_uuid)


class RealGradeReportConformanceTest(SharedModuleStoreTestCase):
    """
    Run the real grade report generator against a small fixture course in the
    modulestore and assert the stored CSV conforms to the contract.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = CourseFactory.create(org="NAU", course="CONF101", run="2026_T1")

    def test_grade_report_is_learner_grain(self):
        """
        grade_report carries a Username column, so it is learner grain: base
        columns plus anonymous_user_id first, legacy columns untouched.
        """
        learner = UserFactory(username="grade_learner1")
        CourseEnrollmentFactory(user=learner, course_id=self.course.id, is_active=True)

        with TemporaryDirectory() as tmpdir:
            with override_settings(
                GRADES_DOWNLOAD={
                    "STORAGE_TYPE": "localfs",
                    "BUCKET": "test-grades",
                    "ROOT_PATH": tmpdir,
                },
                NAU_REPORTS_ENABLE_BASE_COLUMNS=True,
            ), patch(CURRENT_TASK_PATCH):
                grades.CourseGradeReport.generate(None, None, self.course.id, {}, "graded")
            reports = _stored_reports(tmpdir)

        grade_reports = {name: rows for name, rows in reports.items() if "grade_report" in name}
        self.assertEqual(len(grade_reports), 1, f"expected one grade report, got {list(reports)}")
        rows = next(iter(grade_reports.values()))
        base = ["NAU", str(self.course.id), "2026_T1"]
        self.assertEqual(rows[0][:4], ["org_id", "course_id", "course_run", "anonymous_user_id"])
        self.assertIn("Username", rows[0])
        learner_row = next(row for row in rows[1:] if learner.username in row)
        self.assertEqual(
            learner_row[:4], base + [anonymous_id_for_user(learner, self.course.id)]
        )
