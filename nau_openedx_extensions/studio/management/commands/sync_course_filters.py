"""
Management command to backfill NauCourseFilter from MongoDB other_course_settings.

This command iterates over all (or selected) courses, reads their
other_course_settings from MongoDB, and populates the NauCourseFilter table
in MySQL. Run this once after deploying the NauCourseFilter model to bring
historical data in sync before the course_published signal takes over.

Sync all courses:
  python manage.py cms sync_course_filters

Sync a specific course:
  python manage.py cms sync_course_filters --course-id course-v1:ORG+ID+Run

Sync from a given index (useful to resume a partial run):
  python manage.py cms sync_course_filters --index 50
"""

import traceback

from django.core.management.base import BaseCommand
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore  # lint-amnesty, pylint: disable=import-error

from nau_openedx_extensions.course_filters.sync import sync_course_filters_for_course


class Command(BaseCommand):
    """
    Backfill NauCourseFilter rows for all courses from other_course_settings.
    """

    help = "Backfill NauCourseFilter rows from MongoDB other_course_settings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--course-id",
            type=str,
            default=None,
            help="Sync a single course by its course key string (e.g. course-v1:ORG+ID+Run)",
        )
        parser.add_argument(
            "--index",
            type=int,
            default=0,
            help="Start index of courses to process (useful to resume a partial run)",
        )

    def log_msg(self, msg):
        self.stdout.write(str(msg))
        self.stdout.flush()

    def handle(self, *args, **options):
        """Execute the command."""
        single_course_id = options.get("course_id")

        if single_course_id:
            course_ids = [single_course_id]
        else:
            module_store = modulestore()
            courses = module_store.get_courses()
            course_ids = sorted(str(c.id) for c in courses)

        start_index = options.get("index", 0)
        total = len(course_ids)
        totals = {"created": 0, "deleted": 0, "unchanged": 0, "errors": 0}

        self.log_msg(f"Syncing course filters for {total} course(s) starting at index {start_index}.")

        for index in range(start_index, total):
            course_id = course_ids[index]
            self.log_msg(f"[{index + 1}/{total}] Processing {course_id}")

            try:
                course_key = CourseKey.from_string(course_id)
                result = sync_course_filters_for_course(course_key)
                totals["created"] += result["created"]
                totals["deleted"] += result["deleted"]
                totals["unchanged"] += result["unchanged"]

                if result["created"] or result["deleted"]:
                    self.log_msg(
                        f"  created={result['created']} deleted={result['deleted']} unchanged={result['unchanged']}"
                    )
            except Exception:  # pylint: disable=broad-except
                totals["errors"] += 1
                self.log_msg(f"  ERROR processing {course_id}:")
                self.log_msg(traceback.format_exc())

        self.log_msg(
            f"\nDone. created={totals['created']} deleted={totals['deleted']} "
            f"unchanged={totals['unchanged']} errors={totals['errors']}"
        )
