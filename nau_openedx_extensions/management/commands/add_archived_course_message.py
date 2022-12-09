"""
Script that adds a course message for the archived courses.
"""
import datetime
import json
import logging

from common.djangoapps.status.models import (  # lint-amnesty, pylint: disable=import-error
    CourseMessage,
    GlobalStatusMessage,
)
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone, translation
from django.utils.translation import ugettext as _
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore  # lint-amnesty, pylint: disable=import-error

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command that adds a course message for the archived courses, so the students know that they
    are viewing an archived course and even if they view all the activities they wont have right
    to a certificate.

    To execute for a specific course:
    python manage.py lms add_archived_course_message --course_id course-v1:edX+DemoX+Demo_Course

    To change the default messages:
    python manage.py lms add_archived_course_message --messages '{ "pt":"Curso arquivado", "en":"Archived course"}'
    """

    help = (
        "Adds a course message for archived courses"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--course_id",
            type=str,
            default=None,
            required=False,
            help="Course id of the course that needs to be checked if it needs an archived course message",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            required=False,
            help="Number of days the course has been archived",
        )
        parser.add_argument(
            "--messages",
            type=json.loads,
            default=None,
            required=False,
            help="JSON with a dictionary of language and message, to override the default message.",
        )

    def handle(self, *args, **options):
        """
        Adds a course message for the archived courses.
        """
        course_id = options['course_id']
        if course_id:
            course_ids = [course_id]
        else:
            course_ids = self.load_course_ids()

        messages = options['messages'] or {}

        days = options['days']

        for course_id in course_ids:
            print("Handling course_id: " + course_id)
            course_key = CourseKey.from_string(course_id)
            course = modulestore().get_course(course_key)
            if Command.is_archived_course(course, days):
                Command.add_course_message(course, messages)
            else:
                Command.remove_course_message(course)

    @staticmethod
    def load_course_ids():
        """
        Load all course ids
        """
        module_store = modulestore()
        courses = module_store.get_courses()
        course_ids = [str(x.id) for x in courses]
        return course_ids

    @staticmethod
    def add_course_message(course, messages):
        """Add a course message """
        cm = Command.get_course_message(course)
        need_save = False
        if not cm:
            print(" creating course message for course: " + str(course.id))
            cm = CourseMessage()
            cm.global_message = Command.get_latest_gs_message()
            cm.course_key = course.id
            need_save = True

        default_message = None
        with translation.override(course.language):
            default_message = _(
                "This is an archived course and no longer allows executing activities to obtain a certificate.")
        if not default_message:
            with translation.override(settings.LANGUAGE_CODE):
                default_message = _(
                    "This is an archived course and no longer allows executing activities to obtain a certificate."
                )

        new_message = messages.get(course.language, default_message)
        if new_message != cm.message:
            cm.message = new_message
            need_save = True
        if need_save:
            cm.save()

    @staticmethod
    def remove_course_message(course):
        """Remove the course message"""
        cm = Command.get_course_message(course)
        if cm:
            print(" deleting course message for course: " + str(course.id))
            cm.delete()

    @staticmethod
    def get_latest_gs_message():
        """
        Get the latest global message object.
        """
        latest_gsmessage = None
        try:
            latest_gsmessage = GlobalStatusMessage.objects.latest("id")
        except GlobalStatusMessage.DoesNotExist:
            # We don't have a course-specific message, so pass.
            pass
        if latest_gsmessage and not latest_gsmessage.enabled:
            latest_gsmessage = None
        if not latest_gsmessage:
            latest_gsmessage = GlobalStatusMessage()
            latest_gsmessage.enabled = True
            latest_gsmessage.save()
        return latest_gsmessage

    @staticmethod
    def get_course_message(course):
        """
        Get current course message or None if it doesn't exist.
        """
        course_home_message = None
        try:
            course_home_message = Command.get_latest_gs_message().coursemessage_set.get(
                course_key=course.id
            )
        except CourseMessage.DoesNotExist:
            # We don't have a course-specific message, so pass.
            pass
        return course_home_message

    @staticmethod
    def is_archived_course(course, days: int) -> bool:
        """
        Check if a course is archived.
        """
        return course.end and (course.end + datetime.timedelta(days) < timezone.now())

    @staticmethod
    def delete_status_messages():
        """
        Delete all Global status messages and its course messages.
        Use it with care.
        """
        for cm in CourseMessage.objects.all():
            cm.delete()
        for m in GlobalStatusMessage.objects.all():
            m.delete()
