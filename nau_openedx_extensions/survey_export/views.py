"""
Views for the survey export API.
"""

from django.utils.translation import gettext as _
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthentication
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from nau_openedx_extensions.certificate_export.views import validate_course_access
from nau_openedx_extensions.survey_export.tasks import export_course_surveys_task

# Constants for response messages
SUCCESS_MESSAGE = _("Export task started successfully.")


class SurveyExportAPIView(APIView):
    """
    API view to export the responses of every Survey component of a course as one CSV file.

    This view only has a POST method that initiates the survey export task for a given course.
    It allows the same users as the certificate export.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, course_id: str) -> Response:
        """
        Start a survey export task for a course.

        Args:
            request (Request): The HTTP request object
            course_id (str): The ID of the course to export the survey responses for

        Returns:
            Response: A response indicating the task has started
        """
        is_valid, result = validate_course_access(request, course_id)
        if not is_valid:
            return result  # type: ignore

        export_course_surveys_task.delay(course_id)
        return Response({"success": True, "message": SUCCESS_MESSAGE})
