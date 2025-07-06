"""
Student backend abstraction
"""

from __future__ import absolute_import, unicode_literals

from importlib import import_module

from django.conf import settings


def get_student_course_enrollment_allowed(user, course_id, *args, **kwargs):
    """
    Get the student CourseEnrollmentAllowed class instance from the edx-platform.

    Args:
        user: The user id to find the CourseEnrollmentAllowed instance.
        course_id: The course id to find the CourseEnrollmentAllowed instance.

    Returns:
        A CourseEnrollmentAllowed instance or None
    """
    backend_module = settings.NAU_STUDENT_MODULE
    backend = import_module(backend_module)
    return backend.get_student_course_enrollment_allowed(user, course_id, *args, **kwargs)


def get_enrollment(user, course_key, *args, **kwargs):
    """
    Gets the student CourseEnrollment class from the edx-platform.
    This class represents an user enrolled in a course.

    Args:
        user: The user id to find the Enrollment.
        course_key: The course key to find the Enrollment.
    """
    backend_module = settings.NAU_STUDENT_MODULE
    backend = import_module(backend_module)
    return backend.get_enrollment(user, course_key, *args, **kwargs)


def get_course_instructor_role():
    """
    Wrapper for `common.djangoapps.student.roles.CourseInstructorRole` in edx-platform.
    """
    backend_function = settings.NAU_STUDENT_MODULE
    backend = import_module(backend_function)
    return backend.CourseInstructorRole


def get_course_staff_role():
    """
    Wrapper for `common.djangoapps.student.roles.CourseStaffRole` in edx-platform.
    """
    backend_function = settings.NAU_STUDENT_MODULE
    backend = import_module(backend_function)
    return backend.CourseStaffRole


def get_course_enrollment_model():
    """
    Wrapper for `common.djangoapps.student.models.course_enrollment.CourseEnrollment` in edx-platform.
    """
    backend_function = settings.NAU_STUDENT_MODULE
    backend = import_module(backend_function)
    return backend.CourseEnrollment


CourseInstructorRole = get_course_instructor_role()
CourseStaffRole = get_course_staff_role()
CourseEnrollment = get_course_enrollment_model()
