"""URL patterns for certificate export endpoints."""

from django.urls import re_path

from nau_openedx_extensions.certificate_export import views

urlpatterns = [
    re_path(
        r"^courses/(?P<course_id>[^/]+)/csv$",
        views.CertificateExportAPIView.as_view(),
        name="nau_export_certificates_csv",
    ),
    re_path(
        r"^courses/(?P<course_id>[^/]+)/pdf$",
        views.CertificateExportPdfAPIView.as_view(),
        name="nau_export_certificates_pdf",
    ),
]
