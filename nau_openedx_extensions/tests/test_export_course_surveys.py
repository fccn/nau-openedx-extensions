"""
Tests for the export_course_surveys management command.

They run the command against real Survey XBlocks (from xblock-poll, the
package NAU deploys) in a modulestore fixture course, so an upstream change in
how the block stores its answers surfaces here instead of as an empty report.
"""

import csv
import json
import os
from io import StringIO
from tempfile import TemporaryDirectory

from common.djangoapps.student.tests.factories import UserFactory  # pylint: disable=import-error
from django.core.management.base import CommandError, OutputWrapper
from django.test.utils import override_settings
from lms.djangoapps.courseware.models import StudentModule  # pylint: disable=import-error
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase  # pylint: disable=import-error
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory  # pylint: disable=import-error

from nau_openedx_extensions.management.commands.export_course_surveys import Command

QUESTIONS = [
    ["enjoy", {"label": "Are you enjoying the course?", "img": None, "img_alt": None}],
    ["recommend", {"label": "Would you recommend this course?", "img": None, "img_alt": None}],
]
ANSWERS = [["Y", "Yes"], ["N", "No"], ["M", "Maybe"]]


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


def _run_command(*course_ids):
    """
    Run the command with a captured stdout and return the output text.
    """
    command = Command()
    output = StringIO()
    command.stdout = OutputWrapper(output)
    command.handle(course_ids=list(course_ids))
    return output.getvalue()


def _answer(user, block, choices):
    """
    Store ``user``'s survey ``choices`` for ``block`` as the LMS would.
    """
    return StudentModule.objects.create(
        student=user,
        course_id=block.scope_ids.usage_id.course_key,
        module_state_key=block.scope_ids.usage_id,
        module_type="survey",
        state=json.dumps({"choices": choices}),
    )


class ExportCourseSurveysTest(SharedModuleStoreTestCase):
    """
    Conformance tests for the aggregated survey report.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.course = CourseFactory.create(org="NAU", course="SURV101", run="2026_T1")
        with cls.store.bulk_operations(cls.course.id):
            chapter = BlockFactory.create(parent=cls.course, category="chapter")
            sequential = BlockFactory.create(parent=chapter, category="sequential")
            vertical = BlockFactory.create(parent=sequential, category="vertical")
            cls.survey = BlockFactory.create(
                parent=vertical,
                category="survey",
                block_name="Course feedback",
                questions=QUESTIONS,
                answers=ANSWERS,
            )

    def _generate(self, **extra_settings):
        """Run the command and return (stored survey report rows, output)."""
        with TemporaryDirectory() as tmpdir:
            with override_settings(
                GRADES_DOWNLOAD={
                    "STORAGE_TYPE": "localfs",
                    "BUCKET": "test-grades",
                    "ROOT_PATH": tmpdir,
                },
                **extra_settings,
            ):
                output = _run_command(str(self.course.id))
            reports = _stored_reports(tmpdir)
        survey_reports = {name: rows for name, rows in reports.items() if "survey_report" in name}
        if not survey_reports:
            return None, output
        assert len(survey_reports) == 1, f"expected one survey report, got {list(reports)}"
        return next(iter(survey_reports.values())), output

    def test_aggregated_long_format(self):
        """
        One row per learner and question, with the answer labels resolved,
        ordered by most recent state; unanswered questions get an empty cell.
        """
        learner = UserFactory(username="survey_learner1")
        partial = UserFactory(username="survey_learner2")
        _answer(learner, self.survey, {"enjoy": "Y", "recommend": "M"})
        _answer(partial, self.survey, {"enjoy": "N"})

        rows, output = self._generate()

        self.assertEqual(rows[0], ["username", "block_id", "block_name", "question", "answer"])
        by_learner_question = {(row[0], row[3]): row for row in rows[1:]}
        block_id = str(self.survey.scope_ids.usage_id)
        self.assertEqual(
            by_learner_question[("survey_learner1", "Are you enjoying the course?")],
            ["survey_learner1", block_id, "Course feedback", "Are you enjoying the course?", "Yes"],
        )
        self.assertEqual(
            by_learner_question[("survey_learner1", "Would you recommend this course?")][-1],
            "Maybe",
        )
        self.assertEqual(
            by_learner_question[("survey_learner2", "Would you recommend this course?")][-1],
            "",
        )
        self.assertIn("exported 4 answers from 1 survey block(s)", output)

    def test_only_latest_state_counts(self):
        """
        A learner who answered twice appears once, with the latest choices
        (resubmissions update the learner's single StudentModule row).
        """
        learner = UserFactory(username="survey_learner3")
        student_module = _answer(learner, self.survey, {"enjoy": "N", "recommend": "N"})
        student_module.state = json.dumps({"choices": {"enjoy": "Y", "recommend": "Y"}})
        student_module.save()

        rows, _output = self._generate()

        learner_rows = [row for row in rows[1:] if row[0] == learner.username]
        self.assertEqual(len(learner_rows), 2)
        self.assertEqual({row[-1] for row in learner_rows}, {"Yes"})

    def test_identity_columns_prepended_when_enabled(self):
        """
        The report goes through the platform upload helper, so the identity
        block applies when NAU_REPORTS_ENABLE_BASE_COLUMNS is on.
        """
        learner = UserFactory(username="survey_learner4")
        _answer(learner, self.survey, {"enjoy": "Y", "recommend": "Y"})

        rows, _output = self._generate(NAU_REPORTS_ENABLE_BASE_COLUMNS=True)

        self.assertEqual(
            rows[0][:4], ["course_id", "email", "username", "student_id"]
        )
        learner_row = next(row for row in rows[1:] if row[4] == learner.username)
        self.assertEqual(
            learner_row[:4],
            [str(self.course.id), learner.email, learner.username, str(learner.id)],
        )

    def test_course_without_surveys_generates_nothing(self):
        """
        A course with no survey blocks produces no file and says so.
        """
        empty_course = CourseFactory.create(org="NAU", course="NOSURV", run="2026_T1")

        with TemporaryDirectory() as tmpdir:
            with override_settings(
                GRADES_DOWNLOAD={
                    "STORAGE_TYPE": "localfs",
                    "BUCKET": "test-grades",
                    "ROOT_PATH": tmpdir,
                },
            ):
                output = _run_command(str(empty_course.id))
            reports = _stored_reports(tmpdir)

        self.assertEqual(reports, {})
        self.assertIn("no survey blocks found", output)

    def test_invalid_course_id_fails_before_exporting(self):
        """
        An invalid course id aborts the run with a CommandError.
        """
        with self.assertRaises(CommandError):
            _run_command("not-a-course-id")
