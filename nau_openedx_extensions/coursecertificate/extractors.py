"""
This module is used to extract the data from the certificate.
"""

from django.conf import settings

from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview
from nau_openedx_extensions.edxapp_wrapper.student import CourseEnrollment


def certificate_date(certificate) -> str:
    """
    Extract the creation date from a certificate.

    Args:
        certificate (GeneratedCertificate): The certificate object.

    Returns:
        str: The certificate creation date in ISO format.
    """
    return str(certificate.created_date.isoformat())


def certificate_url(certificate) -> str:
    """
    Generate the public URL for a certificate.

    Args:
        certificate (GeneratedCertificate): The certificate object

    Returns:
        str: The complete URL to access the certificate in the LMS.
    """
    return f"{settings.LMS_ROOT_URL}/certificates/{certificate.verify_uuid}"


def course_id(certificate) -> str:
    """
    Extract the course ID from a certificate.

    Args:
        certificate (GeneratedCertificate): The certificate object.

    Returns:
        str: The course ID as a string.
    """
    return str(certificate.course_id)


def course_code(certificate) -> str:
    """
    Extract the course code from a certificate.

    Args:
        certificate (GeneratedCertificate): The certificate object.

    Returns:
        str: The course code (course part of the course ID).
    """
    return certificate.course_id.course


def course_name(certificate) -> str:
    """
    Extract the display name of the course from a certificate.

    If the course is not found, unknown is returned.

    Args:
        certificate (GeneratedCertificate): The certificate object.

    Returns:
        str: The display name of the course, or unknown if the course is not found.
    """
    course = CourseOverview.objects.filter(id=certificate.course_id).first()
    return course.display_name if course else "unknown"


def student_email(certificate) -> str:
    """
    Extract the student's email address from a certificate.

    Args:
        certificate (GeneratedCertificate): The certificate object.

    Returns:
        str: The student's email address.
    """
    return certificate.user.email


def student_username(certificate) -> str:
    """
    Extract the student's username from a certificate.

    Args:
        certificate (GeneratedCertificate): The certificate object.

    Returns:
        str: The student's username.
    """
    return certificate.user.username


def student_name(certificate) -> str:
    """
    Extract the student's full name from a certificate.

    Args:
        certificate (GeneratedCertificate): The certificate object.

    Returns:
        str: The student's full name from their profile.
    """
    return certificate.user.profile.name


def student_nau_user_extended_model_field(certificate, field_name: str) -> str | None:
    """
    Extract a specific field from the NAU user extended model.

    This function safely retrieves custom fields from the NAU-specific
    user extended model if it exists for the user.

    Args:
        certificate (GeneratedCertificate): The certificate object.
        field_name (str): The name of the field to extract from the extended model.

    Returns:
        str | None: The value of the requested field, or None if the extended
            model doesn't exist or the field is not found.
    """
    if hasattr(certificate.user, "nauuserextendedmodel"):
        return getattr(certificate.user.nauuserextendedmodel, field_name, None)
    return None


def student_enrolled_date(certificate) -> str | None:
    """
    Extract the student's enrollment date for the course.

    Args:
        certificate (GeneratedCertificate): The certificate object.

    Returns:
        str | None: The enrollment date in ISO format, or None if enrollment record is not found.
    """
    course_enrollment = CourseEnrollment.objects.filter(user=certificate.user, course_id=certificate.course_id).first()
    return course_enrollment.created.isoformat() if course_enrollment else None
