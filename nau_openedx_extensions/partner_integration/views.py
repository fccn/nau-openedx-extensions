"""Views for data extraction endpoints."""
import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.shortcuts import redirect
from oauth2_provider.models import get_application_model
from oauth2_provider.views import AuthorizationView
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from nau_openedx_extensions.models import SSOPartnerIntegration
from nau_openedx_extensions.partner_integration.exception import (
    PartnerIntegrationCourseOwnerException,
    PartnerIntegrationDataConflictException,
    PartnerIntegrationInactiveClientException,
    PartnerIntegrationInternalErrorException,
    PartnerIntegrationInvalidDataProvidedException,
    PartnerIntegrationNoDataProvidedException,
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

Application = get_application_model()


class DataExtractorPagination(PageNumberPagination):
    """
    Custom pagination for data extraction endpoints.

    Attributes:
        page_size (int): Default number of items per page (100).
        page_size_query_param (str): Query parameter name to allow client to override page size.
        max_page_size (int): Maximum allowed page size (100) to prevent large queries.
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
        logger.info("PartnerClientTokenView: POST request received. Staring authentication process.")
        client_id = request.headers.get("X-Client-ID")
        auth_header = request.headers.get("Authorization")

        if not client_id or not auth_header:
            logger.error("PartnerClientTokenView: Missing client_id or Authorization header.")
            return Response({"detail": "Missing client_id or Authorization header"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            scheme, client_secret = auth_header.split(" ")
        except ValueError as e:
            logger.error("PartnerClientTokenView: Invalid Authorization header format.", exc_info=e)
            return Response({"detail": "Invalid Authorization header"}, status=status.HTTP_400_BAD_REQUEST)

        if scheme.lower() != "token":
            return Response({"detail": "Authorization scheme must be Token"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = PartnerAPIClient.objects.get(client_id=client_id, is_active=True)
        except BaseException as e:
            logger.error(f"PartnerClientTokenView: Client with ID {client_id} not found or inactive.", exc_info=e)
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
        PartnerIntegrationInactiveClientException: An exception raised when the client is inactive.
        PartnerIntegrationNoDataProvidedException: An exception raised when no data is provided for the query.
        PartnerIntegrationInternalErrorException: An exception raised when an internal error occurs.

    Methods:
        post: Handles POST requests to retrieve certificates.

    Example of payload:
        {
            "start_date": "2025-08-16",
            "end_date": "2025-09-16",
            "usernames": [
                "user1",
                "user2"
            ],
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
                logger.error("CertificateRestExportView: Inactive client attempted to access endpoint.")
                raise PartnerIntegrationInactiveClientException()

            serializer = DataExtractorRequestSerializer(
                data=request.data, context={
                    "query_security_scope": query_security_scope})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            certificate_ids = CertificateExportFacade().get_certificates(
                query_security_scope,
                validated_data.get("start_date"),
                validated_data.get("end_date"),
                validated_data.get("courses"),
                validated_data.get("nifs"),
                validated_data.get("emails"),
                validated_data.get("usernames")
            )

            paginator = self.pagination_class()
            paginated_certificate_ids = paginator.paginate_queryset(certificate_ids, request)
            certificates_page = CertificateExportFacade().apply_heavy_operations(
                paginated_certificate_ids)
            serializer = CompleteCertificateDataSerializer(certificates_page, many=True)
            response = paginator.get_paginated_response(serializer.data)

            return response
        except PartnerIntegrationInvalidDataProvidedException as e:
            logger.exception(
                "Invalid data provided for certificate export", exc_info=e
            )
            return Response(
                {"error": e.message}, status=status.HTTP_400_BAD_REQUEST
            )
        except PartnerIntegrationNoDataProvidedException as e:
            logger.exception(
                "No data provided for certificate export", exc_info=e
            )
            return Response(
                {"error": e.message}, status=status.HTTP_400_BAD_REQUEST
            )
        except PartnerIntegrationInternalErrorException as e:
            logger.exception(
                "Internal error occurred during certificate export", exc_info=e
            )
            return Response(
                {"error": e.message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error occurred during certificate export", exc_info=e
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EnrollmentRestExportView(APIView):
    """
    EnrollmentRestExportView is an endpoint to retrieve enrollments based on provided specific parameters,
    or based on the client's query security scope.

    Example of payload:
        {
            "start_date": "2025-08-16",
            "end_date": "2025-09-16",
            "usernames": [
                "user1",
                "user2"
            ],
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
                logger.error("EnrollmentRestExportView: Inactive client attempted to access endpoint.")
                raise PartnerIntegrationInactiveClientException()

            serializer = DataExtractorRequestSerializer(
                data=request.data, context={
                    "query_security_scope": query_security_scope})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            enrollment_ids = EnrollmentFacade().get_enrollments(
                query_security_scope,
                validated_data.get("start_date"),
                validated_data.get("end_date"),
                validated_data.get("courses"),
                validated_data.get("nifs"),
                validated_data.get("emails"),
                validated_data.get("usernames")
            )

            paginator = self.pagination_class()
            paginated_enrollment_ids = paginator.paginate_queryset(enrollment_ids, request)
            enrollments_page = EnrollmentFacade().apply_heavy_operations(paginated_enrollment_ids)

            serializer = CompleteEnrollmentDataSerializer(enrollments_page, many=True)
            response = paginator.get_paginated_response(serializer.data)

            return response
        except PartnerIntegrationInvalidDataProvidedException as e:
            logger.exception(
                "Invalid data provided for enrollment export", exc_info=e
            )
            return Response(
                {"error": e.message}, status=status.HTTP_400_BAD_REQUEST
            )
        except PartnerIntegrationNoDataProvidedException as e:
            logger.exception(
                "No data provided for enrollment export", exc_info=e
            )
            return Response(
                {"error": e.message}, status=status.HTTP_400_BAD_REQUEST
            )
        except PartnerIntegrationInternalErrorException as e:
            logger.exception(
                "Internal error occurred during enrollment export", exc_info=e
            )
            return Response(
                {"error": e.message},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error occurred during enrollment export", exc_info=e
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StudentProgressRestExportView(APIView):
    """
    Endpoint to retrieve student progress based on provided specific parameters,
    or based on the client's query security scope.
    """
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsAuthenticatedPartnerAPIClient]

    def post(self, request):
        """
        Handles POST requests to retrieve student progress based on provided
        parameters.

        Example of payload:
        {
            "course": "course-v1:edX+DemoX+Demo_Course",
            "nif": "123456789"
        }
        or
        {
            "course": "course-v1:edX+DemoX+Demo_Course",
            "email": "user@example01.com"
        }
        or
        {
            "course": "course-v1:edX+DemoX+Demo_Course",
            "username": "user01"
        }
        """
        try:
            logger.info("StudentProgressRestExportView: POST request received.")
            client: PartnerAPIClient = request.partner_client
            query_security_scope: dict = client.query_security_scope

            if not client.is_active:
                raise PartnerIntegrationInactiveClientException()

            course = request.data.get("course")
            student_id = request.data.get("student_id")
            nif = request.data.get("nif")
            email = request.data.get("email")
            username = request.data.get("username")

            if not course:
                return Response({"error": "Invalid request data, it must to have a valid course id."},
                                status=status.HTTP_400_BAD_REQUEST)
            elif not student_id and not nif and not email and not username:
                return Response(
                    {
                        "error": (
                            "Invalid request data, it must to have one of the user's "
                            "identifier: id, nif, email or username."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            student_progress_facade = StudentProgressExportFacade()
            student_progress = student_progress_facade.get_student_progress(
                course,
                student_id,
                nif,
                email,
                username,
                query_security_scope
            )
            data = CourseProgressSerializer(student_progress).data

            return Response(data)
        except PartnerIntegrationCourseOwnerException as e:
            logger.error(
                "StudentProgressRestExportView: Client does not have permisson to access this course.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationNoDataProvidedException as e:
            logger.error(
                "StudentProgressRestExportView: No data provided for student progress export.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationInternalErrorException as e:
            logger.error(
                "StudentProgressRestExportView: Internal error occurred during student progress export.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "StudentProgressRestExportView: Unexpected error occurred during student progress export.", exc_info=e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PartnerRestIntegrationEnrollUserView(APIView):
    """
    Endpoint to enroll users via REST API.
    """
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsAuthenticatedPartnerAPIClient]

    def post(self, request):
        """
        HTTP POST handler to enroll user based on provided parameters.
        It accepts a course ID, NIF or emails to enroll user in the specified course.

        Returns:
            list: The enrollment register created.

        Example of payload:
        {
            "course": "course-v1:edX+DemoX+Demo_Course",
            "nif": "123456789"
        }
        or
        {
            "course": "course-v1:edX+DemoX+Demo_Course",
            "email": "user@example01.com"
        }
        """
        try:
            logger.info("PartnerRestIntegrationEnrollmentView: POST request received.")
            client: PartnerAPIClient = request.partner_client
            query_security_scope: dict = client.query_security_scope

            if not client.is_active:
                logger.error("PartnerRestIntegrationEnrollmentView: Inactive client attempted to access endpoint.")
                raise PartnerIntegrationInactiveClientException()

            serializer = EnrollUserRequestSerializer(
                data=request.data, context={
                    "query_security_scope": query_security_scope})
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            enrollment = EnrollmentFacade().enroll_user(
                query_security_scope,
                validated_data.get("course"),
                validated_data.get("nif"),
                validated_data.get("email"),
                validated_data.get("username")
            )
            serializer = CompleteEnrollmentDataSerializer(enrollment)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except PartnerIntegrationDataConflictException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: Data conflict occurred during enrollment.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_409_CONFLICT)
        except PartnerIntegrationInvalidDataProvidedException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: Invalid data provided for enrollment.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationNoDataProvidedException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: No data provided for enrollment.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationInternalErrorException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: Internal error occurred during enrollment.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "PartnerRestIntegrationEnrollmentView: Unexpected error occurred during enrollment.", exc_info=e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomAuthorizationView(AuthorizationView):
    """
    Full override of the authorization screen and decisions.
    """

    DEFAULT_PARTNER_SSO_REDIRECT_URI = getattr(
        settings,
        "DEFAULT_PARTNER_SSO_REDIRECT_URI",
        "https://www.nau.edu.pt"
    )

    def get(self, request, *args, **kwargs):
        """Get method that starts the SSO process"""
        try:
            sso_client_id = request.GET.get("client_id")
            redirect_uri = request.GET.get("redirect_uri")
            external_user_id = request.GET.get("external_user_id")

            if not redirect_uri:
                application = Application.objects.get(client_id=sso_client_id)
                if application.redirect_uris:
                    uri = (
                        f"{application.redirect_uris}/?nau_user={request.user.username}"
                        f"&external_user_id={external_user_id}")
                    return redirect(uri)

                return redirect(self.DEFAULT_PARTNER_SSO_REDIRECT_URI)

            redirect_uri = str(redirect_uri).replace(" ", "%2B")
            redirect_uri = str(redirect_uri).replace("+", "%2B")

            return redirect(redirect_uri)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "CustomAuthorizationView: Unexpected error occurred during SSO.", exc_info=e)
            return redirect(self.DEFAULT_PARTNER_SSO_REDIRECT_URI)

    def dispatch(self, request, *args, **kwargs):
        """
        Override of `dispatch` method from oauth package.
        It triggers the authentication process.
        """
        jwt_token = request.GET.get("jwt_token")
        client_id = request.GET.get("client_id")
        external_user_id = request.GET.get("external_user_id")

        try:
            partner_client = ClientJWTAuthentication().validate_token_data_and_return_client(jwt_token)
            # Gets the application, if it does not exists throws an exception
            Application.objects.get(client_id=client_id)
            sso_register = SSOPartnerIntegration.objects.get(
                external_user_id=external_user_id, partner_client=partner_client)

            if not sso_register.partner_client.is_active:
                raise PartnerIntegrationInactiveClientException()

            authenticate(request=request)
            if not request.user.is_authenticated:
                login(request, sso_register.user, backend="django.contrib.auth.backends.ModelBackend")
        except Application.DoesNotExist:
            return redirect(self.DEFAULT_PARTNER_SSO_REDIRECT_URI)
        except SSOPartnerIntegration.DoesNotExist:
            return self.handle_sso_registration(request.user, external_user_id, client_id, jwt_token)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "CustomAuthorizationView: Unexpected error occurred during SSO.", exc_info=e)
            return redirect(self.DEFAULT_PARTNER_SSO_REDIRECT_URI)

        return super().dispatch(request, *args, **kwargs)

    def handle_sso_registration(self, user, external_user_id, sso_client_id, jwt_token):
        """This method handles the SSO register. It creates a new register
        if it does not exists, otherwise it updates the external user identification.
        """
        try:
            User = get_user_model()
            if not isinstance(user, User):
                return self.handle_no_permission()

            partner_client = ClientJWTAuthentication().validate_token_data_and_return_client(jwt_token)
            sso_register = SSOPartnerIntegration.objects.filter(user=user, partner_client=partner_client)
            if not sso_register.exists():
                sso_register = SSOPartnerIntegration.objects.create(
                    partner_client=partner_client,
                    user=user,
                    external_user_id=external_user_id,
                )
            else:
                sso_register = sso_register.first()
                sso_register.external_user_id = external_user_id
                sso_register.save()

            application = Application.objects.get(client_id=sso_client_id)
            uri = (
                f"{application.redirect_uris}/?nau_user={user.username}"
                f"&external_user_id={external_user_id}")
            return redirect(uri)
        except Exception as e:
            raise e
