"""
Student backend abstraction
"""
from __future__ import absolute_import, unicode_literals

from importlib import import_module

from django.conf import settings


def get_student_course_enrollment_allowed(user, course_id, *args, **kwargs):
    """
    Gets the student CourseEnrollmentAllowed class from the edx-platform.
    This class represents an user represented by its email address that is
    allowed to enroll in a course.
    """

    backend_module = settings.NAU_STUDENT_MODULE
    backend = import_module(backend_module)

    return backend.get_student_course_enrollment_allowed(user, course_id, *args, **kwargs)
