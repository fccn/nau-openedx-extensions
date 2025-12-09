""" Course block backend abstraction for Teak and later releases.

This backend avoids importing CMS modules directly to prevent circular import issues
that occur in Teak with the content.search module.
"""

import logging

from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore  # pylint: disable=import-error

log = logging.getLogger(__name__)


def get_other_course_settings(course_id):
    """Get Other Course Settings.
    
    This version directly accesses the course.other_course_settings attribute
    instead of using CourseMetadata.fetch_all() from CMS, which causes
    import issues in Teak due to the content.search module.
    """
    try:
        course = modulestore().get_course(course_id)
        if course is None:
            log.error(f'Course not found: {course_id}')
            return {}
        # Access other_course_settings directly from the course object
        # This returns a dict with 'value' key containing the actual settings
        other_course_settings = getattr(course, 'other_course_settings', {})
        # Wrap in the expected format if it's not already
        if other_course_settings and 'value' not in other_course_settings:
            return {'value': other_course_settings}
        return {'value': other_course_settings} if other_course_settings else {}
    except Exception as e:  # pylint: disable=broad-except
        log.error(f'Error fetching other_course_settings for {course_id}: {e}')
        return {}


def get_course_name(course_id):
    """Get the course name."""
    try:
        course = modulestore().get_course(course_id)
        if course is None:
            log.error(f'Course not found: {course_id}')
            return ""
        return course.display_name_with_default
    except Exception as e:  # pylint: disable=broad-except
        log.error(f'Error fetching course {course_id}: {e}')
        return ""


def get_course(course_key: CourseKey):
    """Get the course object."""
    try:
        return modulestore().get_course(course_key)
    except Exception as e:  # pylint: disable=broad-except
        log.error(f'Error fetching course {course_key}: {e}')
        return None
