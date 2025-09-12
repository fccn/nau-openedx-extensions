"""Views for data extraction endpoints."""
import logging

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from nau_openedx_extensions.partner_integration.exception import (
    CertificateInactiveClientException,
    CertificateInternalErrorException,
    CertificateInvalidDataProvidedException,
    CertificateNoDataProvidedException,
    PartnerCourseOwnerException,
)
from nau_openedx_extensions.partner_integration.facade import (
    CertificateExportFacade,
    EnrollmentFacade,
    StudentProgressExportFacade,
)
from nau_openedx_extensions.partner_integration.models import PartnerAPIClient
from nau_openedx_extensions.partner_integration.oauth_authentication import (
    ClientJWTAuthentication,
    IsAuthenticatedPartnerAPIClient,
)
from nau_openedx_extensions.partner_integration.serializers import (
    CompleteCertificateDataSerializer,
    CompleteEnrollmentDataSerializer,
    CourseProgressSerializer,
    DataExtractorRequestSerializer,
    EnrollUserRequestSerializer,
)

logger = logging.getLogger(__name__)


class DataExtractorPagination(PageNumberPagination):
    """
    Custom pagination for data extraction endpoints.

    Attributes:
        page_size (int): Default number of items per page (200).
        page_size_query_param (str): Query parameter name to allow client to override page size.
        max_page_size (int): Maximum allowed page size (200) to prevent large queries.
    """
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 100


class PartnerClientTokenView(APIView):
    """
    Issue JWT to a PartnerAPIClient using the password field for authentication.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        HTTP POST handler to issue JWT to a PartnerAPIClient.

        Returns:
            dict: A dictionary containing the issued access token.
        """
        client_id = request.headers.get("X-Client-ID")
        auth_header = request.headers.get("Authorization")

        if not client_id or not auth_header:
            return Response({"detail": "Missing client_id or Authorization header"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            scheme, client_secret = auth_header.split(" ")
        except ValueError:
            return Response({"detail": "Invalid Authorization header"}, status=status.HTTP_400_BAD_REQUEST)

        if scheme.lower() != "token":
            return Response({"detail": "Authorization scheme must be Token"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = PartnerAPIClient.objects.get(client_id=client_id, is_active=True)
        except BaseException:
            return Response({"detail": "Invalid client"}, status=status.HTTP_403_FORBIDDEN)

        if not client.check_password(client_secret):
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_403_FORBIDDEN)

        token = ClientJWTAuthentication.issue_client_jwt(client)
        return Response({"access_token": token})


class CertificateRestExportView(APIView):
    """
    Endpoint to retrieve certificates based on provided specific parameters,
    or based on the client's query security scope.

    Raises:
        CertificateInactiveClientException: An exception raised when the client is inactive.
        CertificateNoDataProvidedException: An exception raised when no data is provided for the query.
        CertificateInternalErrorException: An exception raised when an internal error occurs.

    Methods:
        post: Handles POST requests to retrieve certificates.

    Example of payload:
        {
            "start_date": "2025-08-16",
            "end_date": "2025-09-16",
            "nifs": [
                "123456789",
                "987654321"
            ],
            "emails": [
                "user1@example.com",
                "user2@example.com"
            ],
            "courses": [
                "course-v1:edX+DemoX+Demo_Course1",
                "course-v1:edX+DemoX+Demo_Course2"
            ]
        }
    """
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsAuthenticatedPartnerAPIClient]
    pagination_class = DataExtractorPagination

    def post(self, request):
        """
        Handles POST requests to retrieve certificates based on provided parameters
        or client's security scope.

        Returns:
            list: A list of certificates matching the query parameters or query security scope.
        """
        try:
            logger.info("CertificateRestExportView: POST request received.")
            client: PartnerAPIClient = request.partner_client
            query_security_scope: dict = client.query_security_scope

            if not client.is_active:
                raise CertificateInactiveClientException()

            serializer = DataExtractorRequestSerializer(
                data=request.data, context={
                    "query_security_scope": query_security_scope})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            certificates = CertificateExportFacade().get_certificates(
                query_security_scope,
                validated_data.get("start_date"),
                validated_data.get("end_date"),
                validated_data.get("courses"),
                validated_data.get("nifs"),
                validated_data.get("emails")
            )

            paginator = self.pagination_class()
            certificates_page = paginator.paginate_queryset(certificates, request)

            serializer = CompleteCertificateDataSerializer(certificates_page, many=True)
            response = paginator.get_paginated_response(serializer.data)

            return response
        except CertificateInvalidDataProvidedException as e:
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except CertificateNoDataProvidedException as e:
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except CertificateInternalErrorException as e:
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EnrollmentRestExportView(APIView):
    """
    EnrrollmentRestExportView is an endpoint to retrieve enrollments based on provided specific parameters,
    or based on the client's query security scope.
    """
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsAuthenticatedPartnerAPIClient]
    pagination_class = DataExtractorPagination

    def post(self, request):
        """
        HTTP POST handler to retrieve enrollments based on provided parameters
        or client's security scope.

        Returns:
            list: A list of enrollments matching the query parameters or query security scope.
        """
        try:
            logger.info("EnrollmentRestExportView: POST request received.")
            client: PartnerAPIClient = request.partner_client
            query_security_scope: dict = client.query_security_scope

            if not client.is_active:
                raise CertificateInactiveClientException()

            serializer = DataExtractorRequestSerializer(
                data=request.data, context={
                    "query_security_scope": query_security_scope})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            enrollments = EnrollmentFacade().get_enrollments(
                query_security_scope,
                validated_data.get("start_date"),
                validated_data.get("end_date"),
                validated_data.get("courses"),
                validated_data.get("nifs"),
                validated_data.get("emails")
            )

            paginator = self.pagination_class()
            enrollments_page = paginator.paginate_queryset(enrollments, request)

            serializer = CompleteEnrollmentDataSerializer(enrollments_page, many=True)
            response = paginator.get_paginated_response(serializer.data)

            return response
        except CertificateNoDataProvidedException as e:
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except CertificateInternalErrorException as e:
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StudentProgressRestExportView(APIView):
    """
    Endpoint to retrieve student progress based on provided specific parameters,
    or based on the client's query security scope.
    """
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsAuthenticatedPartnerAPIClient]

    def post(self, request):
        """
        Handles POST requests to retrieve certificates based on provided parameters
        or client's security scope.

        Returns:
            list: A list of progresses matching the query parameters or query security scope.
        """
        try:
            logger.info("StudentProgressRestExportView: POST request received.")
            client: PartnerAPIClient = request.partner_client
            query_security_scope: dict = client.query_security_scope

            if not client.is_active:
                raise CertificateInactiveClientException()

            course_id = request.data.get("course_id")
            student_id = request.data.get("student_id")
            nif = request.data.get("nif")
            email = request.data.get("email")

            if not course_id:
                return Response({"error": "Invalid request data, it must to have a valid course id."},
                                status=status.HTTP_400_BAD_REQUEST)
            elif not student_id and not nif and not email:
                return Response(
                    {
                        "error": "Invalid request data, it must to have one of the user's identifier: id, nif or email."},
                    status=status.HTTP_400_BAD_REQUEST)

            student_progress = StudentProgressExportFacade().get_student_progress(
                course_id,
                student_id,
                nif,
                email,
                query_security_scope
            )
            data = CourseProgressSerializer(student_progress).data

            return Response(data)
        except PartnerCourseOwnerException as e:
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except CertificateNoDataProvidedException as e:
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except CertificateInternalErrorException as e:
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PartnerRestIntegrationEnrollUserView(APIView):
    """
    Endpoint to enroll users via REST API
    """
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsAuthenticatedPartnerAPIClient]
    
    def post(self, request):
        """
        HTTP POST handler to enroll users based on provided parameters.
        It accepts a course ID, and a list of NIFs and/or emails to enroll users in the specified course.

        Returns:
            list: A list of enrollments matching the query parameters or query security scope.
        
        Example of payload:
        {
            "course": "course-v1:edX+DemoX+Demo_Course",
            "nifs": [
                "123456789",
                "987654321"
            ],
            "emails": [
                "user@example01.com",
            ]
        }
        """
        try:
            logger.info("PartnerRestIntegrationEnrollmentView: POST request received.")
            client: PartnerAPIClient = request.partner_client
            query_security_scope: dict = client.query_security_scope

            if not client.is_active:
                raise CertificateInactiveClientException()

            serializer = EnrollUserRequestSerializer(
                data=request.data, context={
                    "query_security_scope": query_security_scope})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            enrollments = EnrollmentFacade().enroll_user(
                query_security_scope,
                validated_data.get("course"),
                validated_data.get("nifs"),
                validated_data.get("emails")
            )
            serializer = CompleteEnrollmentDataSerializer(enrollments, many=True)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except CertificateNoDataProvidedException as e:
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except CertificateInternalErrorException as e:
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)