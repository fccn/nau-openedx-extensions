""" urls.py """

from __future__ import absolute_import, unicode_literals

from django.urls import include, re_path

urlpatterns = [
    re_path(r"^certificate-export/", include("nau_openedx_extensions.certificate_export.urls")),
]
