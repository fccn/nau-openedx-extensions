"""
This module is used to extract the data from the certificate.
"""

from django.conf import settings

from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview
from nau_openedx_extensions.edxapp_wrapper.student import CourseEnrollment


def certificate_date(certificate) -> str:
    return str(certificate.created_date.isoformat())


def certificate_url(certificate) -> str:
    return f"{settings.LMS_ROOT_URL}/certificates/{certificate.verify_uuid}"


def course_id(certificate) -> str:
    return str(certificate.course_id)


def course_code(certificate) -> str:
    return certificate.course_id.course


def course_name(certificate) -> str:
    course = CourseOverview.objects.get(id=certificate.course_id)
    return course.display_name


def student_email(certificate) -> str:
    return certificate.user.email


def student_username(certificate) -> str:
    return certificate.user.username


def student_name(certificate) -> str:
    return certificate.user.profile.name


def student_nau_user_extended_model_field(certificate, field_name: str) -> str | None:
    if hasattr(certificate.user, "nauuserextendedmodel"):
        return getattr(certificate.user.nauuserextendedmodel, field_name, None)
    return None


def student_enrolled_date(certificate) -> str:
    course_enrollment = CourseEnrollment.objects.get(user=certificate.user, course_id=certificate.course_id)
    return course_enrollment.created.isoformat()  # type: ignore
