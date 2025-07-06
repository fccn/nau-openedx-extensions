"""
This module is used to extract the data from the course.
"""

from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview


def id(certificate) -> str:  # pylint: disable=redefined-builtin
    return str(certificate.course_id)


def code(certificate) -> str:
    return certificate.course_id.course


def name(certificate) -> str:
    course = CourseOverview.objects.get(id=certificate.course_id)
    return course.display_name
