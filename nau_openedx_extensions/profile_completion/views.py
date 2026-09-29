"""
Views for the profile completion API.
"""

from django.conf import settings
from django.utils.translation import gettext as _
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthentication
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from nau_openedx_extensions.edxapp_wrapper.student import CourseInstructorRole, CourseStaffRole
from nau_openedx_extensions.filters.pipeline import (
    missing_profile_fields,
    profile_completion_account_url,
    profile_field_label,
)

INVALID_COURSE_MESSAGE = _("The supplied course_id key is not valid.")


class ProfileCompletionAPIView(APIView):
    """
    The profile fields a course requires that the requesting learner has not filled in.

    The filters in filters/pipeline.py already keep the learner out of the course
    about page, the enrollment and the course content while fields are missing. This
    exposes the same answer to the MFEs, which cannot work it out on their own: the
    required fields live in the course advanced settings, which no learner-facing API
    returns. The learning MFE uses it to hide the course outline and, for a learner
    who is not enrolled yet, to replace the enrollment messages with a link to the
    account page.

    Staff get an empty list, as they do in RequireProfileFieldsOnXBlockRender, so a
    course team can always open its own course.

    GET /nau-openedx-extensions/profile-completion/courses/<course_id>/

        {
            "missing": [{"name": "nif", "label": "NIF"}],
            "account_url": "https://apps.example.com/account/?missing=nif"
        }

    `account_url` is null when nothing is missing or ACCOUNT_MICROFRONTEND_URL is not
    set.
    """

    authentication_classes = (JwtAuthentication, SessionAuthentication)
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        """
        Return the missing profile fields of the requesting user for `course_id`.
        """
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return Response({"course_id": INVALID_COURSE_MESSAGE}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        is_course_staff = (
            user.is_staff
            or CourseStaffRole(course_key).has_user(user)
            or CourseInstructorRole(course_key).has_user(user)
        )
        missing = [] if is_course_staff else missing_profile_fields(user, course_key)

        account_url = None
        if missing and getattr(settings, "ACCOUNT_MICROFRONTEND_URL", ""):
            account_url = profile_completion_account_url(missing)

        return Response({
            "missing": [{"name": name, "label": profile_field_label(name)} for name in missing],
            "account_url": account_url,
        })
