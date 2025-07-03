"""
This module is used to extract the data from the certificate.
"""


def student_email_certificate(certificate):
    return certificate.user.email


def course_id(certificate):
    return str(certificate.course_id)


def student_nau_user_extended_model_field(certificate, field_name):
    return f"dummy_{field_name}"


def student_username(certificate):
    return certificate.user.username


def certificate_enrolled_date(certificate):
    return str(certificate.created_date)


def certificate_date(certificate):
    return str(certificate.created_date)


def certificate_link(certificate):
    return f"dummy_link_{certificate.id}"
