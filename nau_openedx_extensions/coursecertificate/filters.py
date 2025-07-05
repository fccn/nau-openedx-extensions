"""
This module is used to filter the certificates.
"""

from django.db.models.query import QuerySet


def certificate_by_course_id_regex(certificates: QuerySet, course_id_regex: str) -> QuerySet:
    return certificates.filter(course_id__regex=course_id_regex)


def certificate_by_org(certificates: QuerySet, org: str) -> list:
    return [certificate for certificate in certificates if certificate.course_id.org == org]
