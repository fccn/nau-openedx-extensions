"""
This module is used to extract the data from the student.
"""

from nau_openedx_extensions.edxapp_wrapper.student import CourseEnrollment


def email(certificate) -> str:
    return certificate.user.email


def username(certificate) -> str:
    return certificate.user.username


def name(certificate) -> str:
    return certificate.user.profile.name


def nau_user_extended_model_field(certificate, field_name: str) -> str | None:
    if hasattr(certificate.user, "nauuserextendedmodel"):
        return getattr(certificate.user.nauuserextendedmodel, field_name, None)
    return None


def enrolled_date(certificate) -> str:
    course_enrollment = CourseEnrollment.objects.get(user=certificate.user, course_id=certificate.course_id)
    return course_enrollment.created.isoformat()  # type: ignore
