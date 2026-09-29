""" urls.py """

from __future__ import absolute_import, unicode_literals

from django.urls import include, path, re_path

urlpatterns = [
    re_path(r"^certificate-export/", include("nau_openedx_extensions.certificate_export.urls")),
    re_path(r"^profile-completion/", include("nau_openedx_extensions.profile_completion.urls")),
    path("partner-integration/", include("nau_openedx_extensions.partner_integration.urls")),
]
