"""
Views for the certificate export API.
"""

from __future__ import annotations

from typing import Tuple

from django.utils.translation import gettext as _
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthentication
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from nau_openedx_extensions.certificate_export.management.commands import PDFCommand
from nau_openedx_extensions.certificate_export.tasks import (
    export_course_certificates_task,
    student_answers_values_report_task,
)
from nau_openedx_extensions.edxapp_wrapper.student import CourseDataResearcherRole, CourseStaffRole

# Constants for response messages
SUCCESS_MESSAGE = _("Export task started successfully.")
INVALID_COURSE_MESSAGE = _("The supplied course_id key is not valid.")
NO_PERMISSION_MESSAGE = _("You do not have permission to export certificates for this course.")
MISSING_BLOCK_ID_MESSAGE = _("The block_id field is required.")


def validate_course_access(request: Request, course_id: str) -> Tuple[bool, Response | CourseKey]:
    """
    Validate course access and permissions.

    Args:
        request (Request): The HTTP request object
        course_id (str): The ID of the course to validate

    Returns:
        tuple: (is_valid, response_or_course_key)
            - is_valid: Whether the validation passed
            - response_or_course_key: Either an error Response or the CourseKey
    """
    try:
        course_key = CourseKey.from_string(course_id)
    except InvalidKeyError:
        return False, Response(
            {"course_id": INVALID_COURSE_MESSAGE},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_has_access = any(
        [
            request.user.is_staff,
            CourseStaffRole(course_key).has_user(request.user),
            CourseDataResearcherRole(course_key).has_user(request.user),
        ]
    )

    if not user_has_access:
        return False, Response(
            {
                "success": False,
                "message": NO_PERMISSION_MESSAGE,
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    return True, course_key


class CertificateExportAPIView(APIView):
    """
    API view for exporting CSV course certificates.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, course_id):
        """
        Handles the POST request to export course certificates as a CSV file.
        Args:
            request (Request): The HTTP request object
            course_id (str): The ID of the course to export certificates as CSV
        """
        # Validate course access and permissions
        is_valid, result = validate_course_access(request, course_id)
        if not is_valid:
            return result  # type: ignore
        # Initilize the export task with the course_id
        export_course_certificates_task.delay(course_id)
        return Response({"success": True, "message": SUCCESS_MESSAGE})


class CertificateExportPdfAPIView(APIView):
    """
    API view to export all certificates in PDF format for a given course.

    This view only has a POST method that initiates a PDF export task for a given course.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, course_id: str) -> Response:
        """
        Start a PDF export task for a course.

        Args:
            request (Request): The HTTP request object
            course_id (str): The ID of the course to export certificates for

        Returns:
            Response: A response indicating the task has started
        """
        is_valid, result = validate_course_access(request, course_id)
        if not is_valid:
            return result  # type: ignore

        PDFCommand().handle(course_ids=[course_id])
        return Response({"success": True, "message": SUCCESS_MESSAGE})


class StudentAnswersValuesReportAPIView(APIView):
    """
    API view to generate the Student Answers Values Report for a given course.

    This view accepts a POST request with a block_id in the request body,
    and triggers a Celery task that will:
    1. Find the latest student_state_from_block report in the report store.
    2. Pivot the CSV (one row per answer -> one row per enrollment).
    3. Upload the pivoted CSV to the report store.
    """

    authentication_classes = (SessionAuthentication,)
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, course_id: str) -> Response:
        """
        Start a Student Answers Values Report task for a course.

        Args:
            request (Request): The HTTP request object
            course_id (str): The ID of the course

        Returns:
            Response: A response indicating the task has started
        """
        is_valid, result = validate_course_access(request, course_id)
        if not is_valid:
            return result  # type: ignore

        block_id = request.data.get("block_id")
        if not block_id:
            return Response(
                {"success": False, "message": MISSING_BLOCK_ID_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student_answers_values_report_task.delay(course_id, block_id)
        return Response({"success": True, "message": SUCCESS_MESSAGE})
