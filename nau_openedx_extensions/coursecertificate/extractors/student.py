"""
This module is used to extract the data from the student.
"""


def email(certificate) -> str:
    return certificate.user.email


def username(certificate) -> str:
    return certificate.user.username


def name(certificate) -> str:
    return certificate.user.profile.name


def nau_user_extended_model_field(certificate, field_name) -> str | None:
    if hasattr(certificate.user, "nauuserextendedmodel"):
        return getattr(certificate.user.nauuserextendedmodel, field_name)
    return None


def enrolled_date(certificate) -> str:
    # TODO: Where is the enrolled date?
    return f"{certificate.user.date_joined.isoformat()}"
