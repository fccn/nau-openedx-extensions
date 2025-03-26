"""
Utility functions for courses.
"""
import datetime

from django.utils import timezone
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore  # lint-amnesty, pylint: disable=import-error


def is_course_archived(course, days: int = 0) -> bool:
    """
    Verify if a course is archived.
    Meaning that the course as an end date and the end date is older than the days parameter.

    Parameters:
    course_id: str - The course id
    days: int - Number of days the course has been archived
    """
    end = None
    if hasattr(course, "end"):
        end = course.end
    else:
        course_key = CourseKey.from_string(course)
        module_store_course = modulestore().get_course(course_key)
        end = module_store_course.end
    return end and (end + datetime.timedelta(days) < timezone.now())
