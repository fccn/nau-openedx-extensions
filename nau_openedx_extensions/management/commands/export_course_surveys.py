"""
Export every Survey XBlock's responses of a course to one aggregated CSV in
the `GRADES_DOWNLOAD` storage, where the instructor Data Download section
lists it next to the other course reports.

Phase 2 deliverable (fccn/nau-technical#955, request #791): today survey
responses can only be exported block by block, entering each course — the
Survey XBlock's own "Export Results To CSV" button. This command produces one
course-level file and accepts many course ids, so it scales to the full
catalog.

The report is long format — one row per learner, block and question:

    username, block_id, block_name, question, answer

so surveys with different questions aggregate into the same file. The upload
goes through ``upload_csv_to_report_store``, which means the report identity
columns (course_id, email, username, student_id) are prepended automatically
when ``NAU_REPORTS_ENABLE_BASE_COLUMNS`` is enabled.
"""

import json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from pytz import UTC

from nau_openedx_extensions.edxapp_wrapper.instructor_task import upload_csv_to_report_store

HEADER = ["username", "block_id", "block_name", "question", "answer"]
REPORT_NAME = "survey_report"
SURVEY_CATEGORY = "survey"


class Command(BaseCommand):
    """
    Export all Survey XBlock responses of each course to a CSV report.
    """

    help = (
        "Export all Survey XBlock responses of each course into one CSV in the "
        "report store (instructor Data Download section)."
    )

    def add_arguments(self, parser):
        parser.add_argument("course_ids", nargs="+", metavar="course_id")

    def log_msg(self, msg):
        """Write ``msg`` to stdout immediately."""
        self.stdout.write(msg)
        self.stdout.flush()

    def handle(self, *args, **options):
        """
        Execute the command.
        """
        # pylint: disable=import-error,import-outside-toplevel
        from django.conf import settings
        from lms.djangoapps.courseware.models import StudentModule
        from xmodule.modulestore.django import modulestore

        course_keys = []
        for course_id in options["course_ids"]:
            try:
                course_keys.append(CourseKey.from_string(course_id))
            except InvalidKeyError as error:
                raise CommandError(f"Invalid course id: {course_id}") from error

        for course_key in course_keys:
            start_date = datetime.now(UTC)
            blocks = modulestore().get_items(course_key, qualifiers={"category": SURVEY_CATEGORY})
            if not blocks:
                self.log_msg(f"{course_key}: no survey blocks found, no report generated.")
                continue

            rows = [list(HEADER)]
            for block in blocks:
                rows.extend(self._survey_rows(block, course_key, StudentModule))

            report_name = upload_csv_to_report_store(rows, REPORT_NAME, course_key, start_date)
            lms_root_url = settings.LMS_ROOT_URL
            data_download_url = f"{lms_root_url}/courses/{course_key}/instructor#view-data_download"
            self.log_msg(
                f"{course_key}: exported {len(rows) - 1} answers from {len(blocks)} "
                f"survey block(s) to {report_name or REPORT_NAME}. "
                f"You can confirm the existence of the file on: {data_download_url}"
            )

    @staticmethod
    def _survey_rows(block, course_key, student_module_class):
        """
        Yield one row per learner and question for ``block``.

        Follows the Survey XBlock's own per-block export
        (``SurveyBlock.prepare_data``): answers live in the ``choices`` dict of
        each learner's StudentModule state, keyed by question id; only the most
        recent state per learner counts. Questions the learner did not answer
        (e.g. added after submission) get an empty cell.
        """
        block_id = str(block.scope_ids.usage_id)
        block_name = getattr(block, "block_name", "") or ""
        questions = sorted(block.questions, key=lambda question: question[0])
        answer_labels = dict(block.answers)

        seen = set()
        student_modules = student_module_class.objects.select_related("student").filter(
            course_id=course_key,
            module_state_key=block.scope_ids.usage_id,
        ).order_by("-modified")
        for student_module in student_modules:
            if student_module.student_id in seen:
                continue
            state = json.loads(student_module.state or "{}")
            choices = state.get("choices")
            if not choices:
                continue
            seen.add(student_module.student_id)
            username = student_module.student.username
            for question_id, question in questions:
                answer_id = choices.get(question_id)
                yield [
                    username,
                    block_id,
                    block_name,
                    question.get("label", question_id),
                    answer_labels.get(answer_id, "") if answer_id else "",
                ]
