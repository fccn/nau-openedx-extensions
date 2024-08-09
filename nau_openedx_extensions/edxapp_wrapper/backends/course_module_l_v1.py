""" Course block backend abstraction """

import logging

from cms.djangoapps.models.settings.course_metadata import CourseMetadata  # pylint: disable=import-error
from xmodule.modulestore.django import modulestore  # pylint: disable=import-error

log = logging.getLogger(__name__)

def get_other_course_settings(course_id):
    """Get Other Course Settings."""
    try:
        course = modulestore().get_course(course_id)
        other_course_settings = CourseMetadata.fetch_all(course).get('other_course_settings', {})
    except Exception as e:  # pylint: disable=broad-except
        other_course_settings = {}
        log.error(f'Error fetching other_course_settings for {e}')

    return other_course_settings

def get_course_name(course_id):
    """Get the course name."""
    try:
        course = modulestore().get_course(course_id)
        return course.display_name_with_default
    except Exception as e:  # pylint: disable=broad-except
        log.error(f'Error fetching course {course_id} for {e}')
        return ""
