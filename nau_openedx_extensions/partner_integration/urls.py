"""URL patterns for certificate export endpoints."""

from django.urls import path

from nau_openedx_extensions.partner_integration import views

urlpatterns = [
    path(
        "data-extractor/certificates/",
        views.CertificateRestExportView.as_view(),
        name="nau_data_extractor_certificates"),
    path(
        "data-extractor/student-progress/",
        views.StudentProgressRestExportView.as_view(),
        name="nau_data_extractor_student_progress"),
    path(
        "data-extractor/enrollments/",
        views.EnrollmentRestExportView.as_view(),
        name="nau_data_extractor_enrollments"),
    path(
        "enroll-user/",
        views.PartnerRestIntegrationEnrollUserView.as_view(),
        name="nau_rest_enroll_user"),
    path("auth-token/",
         views.PartnerClientTokenView.as_view(),
         name="nau_partner_client_auth_token"),
    path("sso/authorize/",
         views.CustomAuthorizationView.as_view(),
         name="oauth2_provider_authorize"),
]
