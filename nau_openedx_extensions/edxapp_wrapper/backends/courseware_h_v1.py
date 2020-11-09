""" Courseware backend abstraction """
from courseware.courses import get_course_by_id
from courseware.access import has_access


def get_has_access(*args, **kwargs):
    return has_access


def get_get_course_by_id(*args, **kwargs):
    return get_course_by_id
