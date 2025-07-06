"""
This module is used to extract the data from the certificate.
"""

from django.conf import settings


def date(certificate) -> str:
    return str(certificate.created_date.isoformat())


def url(certificate) -> str:
    return f"{settings.LMS_ROOT_URL}/certificates/{certificate.verify_uuid}"
