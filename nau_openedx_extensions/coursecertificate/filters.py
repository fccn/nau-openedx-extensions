"""
This module is used to filter the certificates.
"""

from django.db.models.query import QuerySet


def certificate_by_course_id_regex(certificates: QuerySet, course_id_regex: str) -> QuerySet:
    """
    Filter certificates by course ID using regex.

    Args:
        certificates (QuerySet): QuerySet of certificates to filter
        course_id_regex (str): Regex to filter course IDs

    Returns:
        QuerySet: Filtered certificates for the specified regex
    """
    return certificates.filter(course_id__regex=course_id_regex)


def certificate_by_org(certificates: QuerySet, org: str) -> QuerySet:
    """
    Filter certificates by organization using Django ORM.

    Args:
        certificates (QuerySet): QuerySet of certificates to filter
        org (str): Organization name to filter by

    Returns:
        QuerySet: Filtered certificates for the specified organization
    """
    org_regex = rf"^course-v1:{org}\+"
    return certificates.filter(course_id__regex=org_regex)
