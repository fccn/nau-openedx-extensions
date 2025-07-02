"""
Mock implementation on getting a student course enrollment allowed.
"""

CourseInstructorRole = None
CourseStaffRole = None
CourseDataResearcherRole = None
CourseEnrollment = None


def get_student_course_enrollment_allowed(user, course_id, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Get the student CourseEnrollmentAllowed class instance from the edx-platform.

    Args:
        user: The user id to find the CourseEnrollmentAllowed instance.
        course_id: The course id to find the CourseEnrollmentAllowed instance.

    Returns:
        A CourseEnrollmentAllowed instance or None
    """
    return None


def get_enrollment(user, course_key, *args, **kwargs):  # pylint: disable=unused-argument
    """
    Gets the student CourseEnrollment class from the edx-platform.
    This class represents an user enrolled in a course.

    Args:
        user: The user id to find the Enrollment.
        course_key: The course key to find the Enrollment.
    """
    return None
