"""URL patterns for survey export endpoints."""

from django.urls import re_path

from nau_openedx_extensions.survey_export import views

urlpatterns = [
    re_path(
        r"^courses/(?P<course_id>[^/]+)/csv$",
        views.SurveyExportAPIView.as_view(),
        name="nau_export_surveys_csv",
    ),
]
