"""
Conformance tests for the grade report certificate-date wrapper.

Same rationale as ``test_base_columns.py``: the wrapper rebinds a function
inside edx-platform modules we do not control, so this suite is what makes an
upstream refactor surface as a test failure instead of silently missing data.
"""

import csv
import os
from datetime import datetime, timezone
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from common.djangoapps.student.tests.factories import (  # pylint: disable=import-error
    CourseEnrollmentFactory,
    UserFactory,
)
from django.conf import settings
from django.test import TestCase
from django.test.utils import override_settings
from lms.djangoapps.certificates.data import CertificateStatuses  # pylint: disable=import-error
from lms.djangoapps.certificates.tests.factories import GeneratedCertificateFactory  # pylint: disable=import-error
from lms.djangoapps.instructor_task.tasks_helper import grades, utils  # pylint: disable=import-error
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase  # pylint: disable=import-error
from xmodule.modulestore.tests.factories import CourseFactory  # pylint: disable=import-error

from nau_openedx_extensions.reports import certificate_date

COURSE_KEY = CourseKey.from_string("course-v1:FCT+CERT101x+2026_T1")
CURRENT_TASK_PATCH = "lms.djangoapps.instructor_task.tasks_helper.runner._get_current_task"


def _csv_file(rows):
    """Return an in-memory text CSV file with ``rows``."""
    source = StringIO(newline="")
    writer = csv.writer(source)
    writer.writerows(rows)
    source.seek(0)
    return source


def _recording_upload(calls, return_value="report_name.csv"):
    """
    Return a plain function with the upload helper's signature that records
    its calls (a real function, not a Mock — see test_base_columns).
    """

    def upload(rows_or_file, csv_name, course_id, timestamp, *args, **kwargs):
        """Record the call and return a canned report name."""
        calls.append((rows_or_file, csv_name, course_id, timestamp, args, kwargs))
        return return_value

    return upload


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


class WrapperBehaviorTest(TestCase):
    """
    Unit tests for the file wrapper and the column transformation.
    """

    def test_setting_defaults_off(self):
        """
        The plugin setting must default to off: shipping the wrapper must not
        change the grade report until the deployment explicitly enables it.
        """
        self.assertFalse(settings.NAU_REPORTS_ENABLE_CERTIFICATE_DATE)

    def test_wrapper_is_passthrough_when_disabled(self):
        """
        With the setting off, the wrapped upload receives the same file object
        and its return value is passed through.
        """
        calls = []
        wrapped = certificate_date._wrap_file(_recording_upload(calls))  # pylint: disable=protected-access
        source = _csv_file([["Username", "Grade"], ["learner1", "0.83"]])

        result = wrapped(source, "grade_report", COURSE_KEY, datetime.now(timezone.utc))

        self.assertEqual(result, "report_name.csv")
        self.assertIs(calls[0][0], source)

    @override_settings(NAU_REPORTS_ENABLE_CERTIFICATE_DATE=True)
    def test_other_reports_left_unchanged(self):
        """
        The wrapper only acts on ``grade_report``: any other csv_name —
        including the companion ``grade_report_err`` — passes through as the
        same file object.
        """
        calls = []
        wrapped = certificate_date._wrap_file(_recording_upload(calls))  # pylint: disable=protected-access
        for csv_name in ("grade_report_err", "problem_grade_report", "student_state"):
            source = _csv_file([["Username"], ["learner1"]])
            wrapped(source, csv_name, COURSE_KEY, datetime.now(timezone.utc))
            self.assertIs(calls[-1][0], source, csv_name)

    @override_settings(NAU_REPORTS_ENABLE_CERTIFICATE_DATE=True)
    def test_column_appended_with_dates(self):
        """
        Learners with a downloadable certificate get its created_date in ISO
        8601; the rest get an empty cell. Legacy columns are untouched.
        """
        learner = UserFactory(username="cert_learner1")
        other = UserFactory(username="cert_learner2")
        certificate = GeneratedCertificateFactory(
            user=learner, course_id=COURSE_KEY, status=CertificateStatuses.downloadable
        )
        calls = []
        wrapped = certificate_date._wrap_file(_recording_upload(calls))  # pylint: disable=protected-access
        source = _csv_file(
            [
                ["Student ID", "Email", "Username", "Grade"],
                [str(learner.id), learner.email, learner.username, "0.83"],
                [str(other.id), other.email, other.username, "0.10"],
            ]
        )

        wrapped(source, "grade_report", COURSE_KEY, datetime.now(timezone.utc))

        rows = list(csv.reader(calls[0][0]))
        self.assertEqual(rows[0], ["Student ID", "Email", "Username", "Grade", "certificate_obtained_date"])
        self.assertEqual(rows[1][-1], certificate.created_date.isoformat())
        self.assertEqual(rows[2][-1], "")

    @override_settings(NAU_REPORTS_ENABLE_CERTIFICATE_DATE=True)
    def test_rows_path_appends_column(self):
        """
        The row-based upload — the path CourseGradeReport actually uses —
        carries the column as well, and other csv_names pass through.
        """
        learner = UserFactory(username="cert_learner4")
        certificate = GeneratedCertificateFactory(
            user=learner, course_id=COURSE_KEY, status=CertificateStatuses.downloadable
        )
        calls = []
        wrapped = certificate_date._wrap_rows(_recording_upload(calls))  # pylint: disable=protected-access
        rows = [["Username", "Grade"], [learner.username, "0.83"]]

        wrapped(rows, "grade_report", COURSE_KEY, datetime.now(timezone.utc))
        wrapped(rows, "student_profile_info", COURSE_KEY, datetime.now(timezone.utc))

        self.assertEqual(
            calls[0][0],
            [
                ["Username", "Grade", "certificate_obtained_date"],
                [learner.username, "0.83", certificate.created_date.isoformat()],
            ],
        )
        self.assertEqual(calls[1][0], rows)

    @override_settings(NAU_REPORTS_ENABLE_CERTIFICATE_DATE=True)
    def test_non_downloadable_certificates_get_empty_cell(self):
        """
        Only delivered (downloadable) certificates count as obtained: other
        statuses leave the cell empty.
        """
        learner = UserFactory(username="cert_learner3")
        GeneratedCertificateFactory(
            user=learner, course_id=COURSE_KEY, status=CertificateStatuses.notpassing
        )
        calls = []
        wrapped = certificate_date._wrap_file(_recording_upload(calls))  # pylint: disable=protected-access
        source = _csv_file([["Username"], [learner.username]])

        wrapped(source, "grade_report", COURSE_KEY, datetime.now(timezone.utc))

        rows = list(csv.reader(calls[0][0]))
        self.assertEqual(rows[1], [learner.username, ""])

    @override_settings(NAU_REPORTS_ENABLE_CERTIFICATE_DATE=True)
    def test_report_without_username_column_left_unchanged(self):
        """
        A CSV without a username column cannot be joined to certificates: the
        wrapper passes the original file through instead of guessing.
        """
        calls = []
        wrapped = certificate_date._wrap_file(_recording_upload(calls))  # pylint: disable=protected-access
        source = _csv_file([["Section", "Enrolled"], ["chapter1", "42"]])

        wrapped(source, "grade_report", COURSE_KEY, datetime.now(timezone.utc))

        self.assertIs(calls[0][0], source)

    def test_wrapper_is_idempotent(self):
        """
        Wrapping an already wrapped upload returns it untouched, so a repeated
        ``ready()`` cannot stack transformations.
        """
        upload = _recording_upload([])
        for wrap in (certificate_date._wrap_rows, certificate_date._wrap_file):  # pylint: disable=protected-access
            wrapped = wrap(upload)
            self.assertIs(wrap(wrapped), wrapped)


class InstallConformanceTest(TestCase):
    """
    Assert the install() rebinding reached the platform namespaces the grade
    report actually calls through.
    """

    def test_uploads_are_wrapped_in_target_namespaces(self):
        """
        AppConfig.ready() already ran; both namespaces must carry the marker
        on both upload helpers.
        """
        for module in (utils, grades):
            for helper in ("upload_csv_to_report_store", "upload_csv_file_to_report_store"):
                self.assertTrue(
                    getattr(getattr(module, helper), "_nau_certificate_date", False),
                    f"{helper} is not wrapped in {module.__name__}",
                )


class RealGradeReportConformanceTest(SharedModuleStoreTestCase):
    """
    Run the real grade report generator against a fixture course and assert
    the stored CSV carries the certificate date, alone and combined with the
    base-columns wrapper.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = CourseFactory.create(org="NAU", course="CERTDATE101", run="2026_T1")

    def _generate(self, **extra_settings):
        """Run the real grade report and return the stored rows."""
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                GRADES_DOWNLOAD={
                    "STORAGE_TYPE": "localfs",
                    "BUCKET": "test-grades",
                    "ROOT_PATH": tmpdir,
                },
                NAU_REPORTS_ENABLE_CERTIFICATE_DATE=True,
                **extra_settings,
            ), patch(CURRENT_TASK_PATCH):
                grades.CourseGradeReport.generate(None, None, self.course.id, {}, "graded")
            reports = _stored_reports(tmpdir)
        grade_reports = {name: rows for name, rows in reports.items() if "grade_report" in name}
        assert len(grade_reports) == 1, f"expected one grade report, got {list(reports)}"
        return next(iter(grade_reports.values()))

    def test_real_grade_report_carries_certificate_date(self):
        """
        The stored grade report ends with certificate_obtained_date: the
        learner with a delivered certificate carries its date, the one
        without carries an empty cell.
        """
        certified = UserFactory(username="certdate_learner1")
        uncertified = UserFactory(username="certdate_learner2")
        for learner in (certified, uncertified):
            CourseEnrollmentFactory(user=learner, course_id=self.course.id, is_active=True)
        certificate = GeneratedCertificateFactory(
            user=certified, course_id=self.course.id, status=CertificateStatuses.downloadable
        )

        rows = self._generate()

        self.assertEqual(rows[0][-1], "certificate_obtained_date")
        certified_row = next(row for row in rows[1:] if certified.username in row)
        uncertified_row = next(row for row in rows[1:] if uncertified.username in row)
        self.assertEqual(certified_row[-1], certificate.created_date.isoformat())
        self.assertEqual(uncertified_row[-1], "")

    def test_composes_with_base_columns(self):
        """
        With both wrappers enabled the report starts with the identity block
        and ends with the certificate date.
        """
        learner = UserFactory(username="certdate_learner3")
        CourseEnrollmentFactory(user=learner, course_id=self.course.id, is_active=True)
        certificate = GeneratedCertificateFactory(
            user=learner, course_id=self.course.id, status=CertificateStatuses.downloadable
        )

        rows = self._generate(NAU_REPORTS_ENABLE_BASE_COLUMNS=True)

        self.assertEqual(rows[0][:4], ["course_id", "email", "username", "student_id"])
        self.assertEqual(rows[0][-1], "certificate_obtained_date")
        learner_row = next(row for row in rows[1:] if learner.username in row)
        self.assertEqual(
            learner_row[:4],
            [str(self.course.id), learner.email, learner.username, str(learner.id)],
        )
        self.assertEqual(learner_row[-1], certificate.created_date.isoformat())
