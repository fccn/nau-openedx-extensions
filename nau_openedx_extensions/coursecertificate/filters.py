"""
This module is used to filter the certificates.
"""

import re


def certificate_by_org(certificates, org):
    return [certificate for certificate in certificates if certificate.course_id.org == org]


def certificate_by_course_id_regex(certificates, course_id_regex):
    return [certificate for certificate in certificates if re.match(course_id_regex, str(certificate.course_id))]
