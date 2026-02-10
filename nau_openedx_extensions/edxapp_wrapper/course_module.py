""" Course block backend abstraction """

import json
import logging

from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)


def get_other_course_settings(course_id):
    """Get Other Course Settings."""
    from xmodule.modulestore.django import modulestore  # pylint: disable=import-error
    try:
        course = modulestore().get_course(course_id)
        other_course_settings = course.other_course_settings or {}
    except Exception as e:  # pylint: disable=broad-except
        other_course_settings = {}
        log.error('Error fetching other_course_settings: %s', e)

    # Normalize shape for callers.
    # Some callers expect `{"value": {...}}`, while modulestore returns `{...}`.
    if isinstance(other_course_settings, str):
        try:
            other_course_settings = json.loads(other_course_settings)
        except Exception:  # pylint: disable=broad-except
            other_course_settings = {}

    if isinstance(other_course_settings, dict) and "value" not in other_course_settings:
        return {"value": other_course_settings}

    return other_course_settings


def get_course_name(course_id):
    """Get the course name."""
    from xmodule.modulestore.django import modulestore  # pylint: disable=import-error
    try:
        course = modulestore().get_course(course_id)
        return course.display_name_with_default
    except Exception as e:  # pylint: disable=broad-except
        log.error(f'Error fetching course {course_id} for {e}')
        return ""


def get_course(course_key: CourseKey):
    """Get the course."""
    from xmodule.modulestore.django import modulestore  # pylint: disable=import-error
    return modulestore().get_course(course_key)
