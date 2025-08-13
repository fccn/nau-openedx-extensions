"""
Real implementation of the certificate backend.
"""

# pylint: disable=import-error, unused-import
from lms.djangoapps.certificates.models import CertificateHtmlViewConfiguration, GeneratedCertificate
from lms.djangoapps.certificates.views.webview import (
    _get_catalog_data_for_course,
    _get_custom_template_and_language,
    _get_user_certificate,
)
