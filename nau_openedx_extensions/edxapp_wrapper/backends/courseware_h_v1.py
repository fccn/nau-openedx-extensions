""" Courseware backend abstraction """
from courseware.access import has_access  # pylint: disable=import-error
from courseware.courses import get_course_by_id  # pylint: disable=import-error


def get_has_access():
    return has_access


def get_get_course_by_id():
    return get_course_by_id
