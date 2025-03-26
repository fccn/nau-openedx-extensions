"""
Dispatch celery tasks that export courses to a tar.gz file.

Warn: this django command won't export the course, it will only dispatch the task to export the course.
Making the CMS celery worker with many pending tasks.
Please check the CMS_URL/heartbeat?extended

Export a specific course:
  python manage.py cms export_course_content_async --username <my_username> <course_id>

Export multiple courses:
  python manage.py cms export_course_content_async --username <my_username> <course_id_1>,<course_id_2>,<course_id_3>

Export all courses:
  python manage.py cms export_course_content_async --username <my_username>

Export not archived courses:
  python manage.py cms export_course_content_async --username <my_username> --skip-archived
"""

import datetime

import pytz
from cms.djangoapps.contentstore.tasks import export_olx  # lint-amnesty, pylint: disable=import-error
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.site_configuration.models import (  # lint-amnesty, pylint: disable=import-error
    SiteConfiguration,
)
from xmodule.modulestore.django import modulestore

from nau_openedx_extensions.utils.course import is_course_archived

User = get_user_model()


class Command(BaseCommand):
    """
    Export all course content to tar.gz and upload it to the course 'GRADES_DOWNLOAD' storage.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            help="The username of the user to export the course content",
        )
        parser.add_argument(
            "--index",
            type=int,
            default=0,
            help="Start index of the course ids to begin exporting",
        )
        parser.add_argument(
            "--skip-archived",
            action="store_true",
            help="Skip archived courses",
        )
        parser.add_argument(
            "course_ids",
            nargs="*",
            metavar="course_id",
            default=None,
            help="Course ids to export or if omitted, all courses will be exported",
        )

    def log_msg(self, msg):
        self.stdout.write(msg)
        self.stdout.flush()

    def handle(self, *args, **options):
        """
        Execute the command
        """
        now = datetime.datetime.now(pytz.UTC)

        course_ids = options.get("course_ids", None)
        if not course_ids:
            module_store = modulestore()
            courses = module_store.get_courses()
            course_ids = [str(x.id) for x in courses]

        username = options.get("username", None)
        user = User.objects.get(username=username)
        user_id = user.id

        start_index = options.get("index", None)
        course_ids.sort()
        courses_count = len(course_ids)
        for index in range(start_index, courses_count):
            course_id = course_ids[index]

            # The `-` caracter of `--skip-archived` is converted to `_` underscore
            if options.get("skip_archived") and is_course_archived(course_id):
                self.log_msg(
                    f"Skipping {index+1} of {courses_count} - exporting {course_id} because it is archived"
                )
                continue

            self.log_msg(
                f"Exporting {index+1} of {courses_count} - exporting {course_id}"
            )
            try:
                course_key = CourseKey.from_string(course_id)

                export_olx.delay(user_id, str(course_key), "en")

                cms_root_url = SiteConfiguration.get_value_for_org(
                    course_key.org, "CMS_ROOT_URL", settings.CMS_ROOT_URL
                )
                to_download_url = f"{cms_root_url}/export/{course_id}"
                self.log_msg(
                    f"You can confirm the existence of the file on: {to_download_url}"
                )
            except Exception as e:
                self.log_msg(f"Error exporting course {course_id}: {e}")
                # print stacktrace and continue
                import traceback

                self.log_msg(traceback.format_exc())
                continue
