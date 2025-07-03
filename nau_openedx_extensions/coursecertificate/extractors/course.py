"""
This module is used to extract the data from the course.
"""


def id(certificate) -> str:  # pylint: disable=redefined-builtin
    return str(certificate.course_id)


def code(certificate) -> str:
    return certificate.course_id.course


def name(certificate) -> str:
    # TODO: Where is the course name?
    return f"{certificate.course_id} display name"
