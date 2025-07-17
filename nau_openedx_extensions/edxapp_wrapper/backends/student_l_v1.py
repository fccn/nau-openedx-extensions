"""
Real implementation on getting a student course enrollment allowed.
"""

# pylint: disable=import-error, unused-import
from common.djangoapps.student.models import CourseEnrollment, CourseEnrollmentAllowed
from common.djangoapps.student.roles import CourseDataResearcherRole


def get_student_course_enrollment_allowed(user, course_id, *args, **kwargs):
    """
    Get the student CourseEnrollmentAllowed class instance from the edx-platform.

    Args:
        user: The user id to find the CourseEnrollmentAllowed instance.
        course_id: The course id to find the CourseEnrollmentAllowed instance.

    Returns:
        A CourseEnrollmentAllowed instance or None
    """
    return CourseEnrollmentAllowed.for_user(user).filter(course_id=course_id).first()

def get_enrollment(user, course_key, *args, **kwargs):
    """
    Gets the student CourseEnrollment class from the edx-platform.
    This class represents an user enrolled in a course.

    Args:
        user: The user id to find the Enrollment.
        course_key: The course key to find the Enrollment.
    """
    return CourseEnrollment.get_enrollment(user, course_key)
