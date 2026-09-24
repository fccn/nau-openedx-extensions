"""URL patterns for the profile completion API."""

from django.urls import re_path

from nau_openedx_extensions.profile_completion import views

urlpatterns = [
    re_path(
        r"^courses/(?P<course_id>[^/]+)/$",
        views.ProfileCompletionAPIView.as_view(),
        name="nau_profile_completion",
    ),
]
