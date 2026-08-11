"""Views for data extraction endpoints."""
import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import IntegrityError
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
    PartnerIntegrationEnrollmentPreventedException,
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
    SSOUserSerializer,
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
        except Exception as e:  # pylint: disable=broad-exception-caught
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
        except PartnerIntegrationInactiveClientException as e:
            logger.error("CertificateRestExportView: Inactive client.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationCourseOwnerException as e:
            logger.error("CertificateRestExportView: Course ownership violation.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationInvalidDataProvidedException as e:
            logger.error("CertificateRestExportView: Invalid data provided.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationNoDataProvidedException as e:
            logger.error("CertificateRestExportView: No data provided.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationInternalErrorException as e:
            logger.error("CertificateRestExportView: Internal error.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("CertificateRestExportView: Unexpected error.", exc_info=e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        except PartnerIntegrationInactiveClientException as e:
            logger.error("EnrollmentRestExportView: Inactive client.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationCourseOwnerException as e:
            logger.error("EnrollmentRestExportView: Course ownership violation.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationInvalidDataProvidedException as e:
            logger.error("EnrollmentRestExportView: Invalid data provided.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationNoDataProvidedException as e:
            logger.error("EnrollmentRestExportView: No data provided.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationInternalErrorException as e:
            logger.error("EnrollmentRestExportView: Internal error.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("EnrollmentRestExportView: Unexpected error.", exc_info=e)
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
        except PartnerIntegrationInactiveClientException as e:
            logger.error("StudentProgressRestExportView: Inactive client.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationCourseOwnerException as e:
            logger.error("StudentProgressRestExportView: Course ownership violation.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationInvalidDataProvidedException as e:
            logger.error("StudentProgressRestExportView: Invalid data provided.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationNoDataProvidedException as e:
            logger.error("StudentProgressRestExportView: No data provided.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationInternalErrorException as e:
            logger.error("StudentProgressRestExportView: Internal error.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("StudentProgressRestExportView: Unexpected error.", exc_info=e)
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
        except PartnerIntegrationInactiveClientException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: Inactive client.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationCourseOwnerException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: Course ownership violation.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationDataConflictException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: Data conflict.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_409_CONFLICT)
        except PartnerIntegrationInvalidDataProvidedException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: Invalid data provided.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationNoDataProvidedException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: No data provided.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)
        except PartnerIntegrationEnrollmentPreventedException as e:
            logger.warning("PartnerRestIntegrationEnrollmentView: Enrollment prevented by filter.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_403_FORBIDDEN)
        except PartnerIntegrationInternalErrorException as e:
            logger.error("PartnerRestIntegrationEnrollmentView: Internal error.", exc_info=e)
            return Response({"error": e.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("PartnerRestIntegrationEnrollmentView: Unexpected error.", exc_info=e)
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

    SSO_LINK_CONFLICT_ERROR = "sso_link_conflict"

    # Marks a request that already restarted the SSO flow once, so the restart is
    # provably a one shot instead of relying only on `logout` having succeeded.
    SSO_SESSION_RESTART_PARAM = "sso_session_restarted"

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
            if request.user.is_authenticated and request.user != sso_register.user:
                # The browser holds a session for a different NAU user than the one this
                # `external_user_id` is linked to. This happens on shared computers, where a
                # previous user left their NAU session open. The link is the authority on who
                # this request belongs to, so the stale session is dropped instead of being
                # used to authorize the partner on the wrong account.
                #
                # The platform refuses to change the user within a single request, so the flow
                # is restarted after the logout. The restarted request carries no session, and
                # follows the regular path of logging in the owner of the register.
                logger.warning(
                    "CustomAuthorizationView: session user does not match the SSO register owner. "
                    "Dropping the existing session and restarting the SSO flow."
                )
                logout(request)

                if request.GET.get(self.SSO_SESSION_RESTART_PARAM):
                    logger.error(
                        "CustomAuthorizationView: the session still belongs to a different user after "
                        "restarting the SSO flow. Aborting instead of restarting it again."
                    )
                    return redirect(self.DEFAULT_PARTNER_SSO_REDIRECT_URI)

                return redirect(self._build_session_restart_url(request))

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
        """This method handles the SSO register. It only creates new registers.

        An existing link is never reassigned here: the authenticated NAU session is not
        proof that the person driving the partner side is the owner of that link. A user
        already linked to this partner with a different `external_user_id`, or an
        `external_user_id` already claimed by another user, is rejected with an
        identifiable error so the partner can inform the user.

        Changing the `external_user_id` of an existing link is an administrative
        operation, served by `PartnerSSOManagementView.patch`.
        """
        try:
            User = get_user_model()
            if not isinstance(user, User):
                return self.handle_no_permission()

            partner_client = ClientJWTAuthentication().validate_token_data_and_return_client(jwt_token)
            application = Application.objects.get(client_id=sso_client_id)

            sso_register = SSOPartnerIntegration.objects.filter(
                user=user, partner_client=partner_client).first()

            if sso_register and sso_register.external_user_id != external_user_id:
                logger.warning(
                    f"CustomAuthorizationView: user '{user.username}' is already linked to partner client "
                    f"'{partner_client.name}' with a different external user ID. Refusing to reassign it."
                )
                return self.handle_sso_link_conflict(application)

            if not sso_register:
                try:
                    SSOPartnerIntegration.objects.create(
                        partner_client=partner_client,
                        user=user,
                        external_user_id=external_user_id,
                    )
                except IntegrityError:
                    logger.warning(
                        f"CustomAuthorizationView: external user ID is already linked to another NAU user "
                        f"for partner client '{partner_client.name}'. Refusing to create a second link."
                    )
                    return self.handle_sso_link_conflict(application)

            uri = (
                f"{application.redirect_uris}/?nau_user={user.username}"
                f"&external_user_id={external_user_id}")
            return redirect(uri)
        except Application.DoesNotExist:
            logger.error(
                f"CustomAuthorizationView: no OAuth application found for client ID '{sso_client_id}'. "
                "Redirecting to the default NAU page."
            )
            return redirect(self.DEFAULT_PARTNER_SSO_REDIRECT_URI)

    def _build_session_restart_url(self, request):
        """Builds the URL of the current request carrying the restart marker."""
        query = request.GET.copy()
        query[self.SSO_SESSION_RESTART_PARAM] = "1"

        return f"{request.path}?{query.urlencode()}"

    def handle_sso_link_conflict(self, application):
        """Redirects back to the partner with an identifiable error.

        The error is sent to the application's registered redirect URI, so the partner
        can tell the user what happened, instead of to the default NAU page where the
        partner would never see it.
        """
        if application.redirect_uris:
            return redirect(f"{application.redirect_uris}/?error={self.SSO_LINK_CONFLICT_ERROR}")

        logger.warning(
            f"CustomAuthorizationView: application '{application.client_id}' has no redirect URI "
            "configured, so the SSO link conflict is reported on the default NAU page, where the "
            "partner cannot read it. Configure a redirect URI for this application."
        )

        return redirect(f"{self.DEFAULT_PARTNER_SSO_REDIRECT_URI}/?error={self.SSO_LINK_CONFLICT_ERROR}")


class PartnerSSOManagementView(APIView):
    """
    Endpoint to manage SSO related operations.
    """
    authentication_classes = [ClientJWTAuthentication]
    permission_classes = [IsAuthenticatedPartnerAPIClient]

    @staticmethod
    def build_register_lookup(client, external_user_id=None, username=None):
        """Builds the query used to find a single SSO register of the given client.

        A register can be addressed either by the partner's own `external_user_id` or by
        the NAU `username`. The username makes the operations solid when the partner no
        longer holds the identifier currently stored on the NAU side.

        Returns:
            tuple: the lookup keyword arguments and a human readable description of it,
                or `(None, None)` when no usable identifier was provided.
        """
        lookup = {"partner_client": client}
        described_as = []

        if external_user_id:
            lookup["external_user_id"] = external_user_id
            described_as.append(f"external_user_id '{external_user_id}'")

        if username:
            lookup["user__username"] = username
            described_as.append(f"username '{username}'")

        if not described_as:
            return None, None

        return lookup, " and ".join(described_as)

    def delete(self, request):
        """
        HTTP DELETE handler to manage SSO operations.
        It accepts an external user ID or a NAU username to remove the SSO register.

        Returns:
            bool: True if the SSO register was successfully removed, False otherwise.

        Example of payload:
        {
            "external_user_id": "external_user_123",
        }

        Or, addressing the same register by its NAU user:
        {
            "username": "nau_user_123",
        }
        """
        described_as = None

        try:
            logger.info("PartnerSSOManagementView: DELETE request received.")

            client: PartnerAPIClient = request.partner_client
            if not client.is_active:
                logger.error("PartnerSSOManagementView: Inactive client attempted to access endpoint.")
                raise PartnerIntegrationInactiveClientException()

            lookup, described_as = self.build_register_lookup(
                client,
                external_user_id=request.data.get("external_user_id"),
                username=request.data.get("username"),
            )

            if not lookup:
                error_message = "An external user ID or a username must be provided to manage SSO."
                logger.error(f"PartnerSSOManagementView: {error_message}")

                return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

            sso_register = SSOPartnerIntegration.objects.get(**lookup)
            sso_register.delete()

            return Response({"success": True}, status=status.HTTP_200_OK)
        except SSOPartnerIntegration.DoesNotExist:
            error_message = f"SSO register with {described_as} not found."
            logger.error(f"PartnerSSOManagementView: {error_message}")

            return Response({"error": error_message}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("PartnerSSOManagementView: Unexpected error.", exc_info=e)
            return Response(
                {"error": "An unexpected error occurred, please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request):
        """
        HTTP PATCH handler to update the external user identification of an SSO register.

        This is the supported way of changing an `external_user_id` that intentionally
        changed on the partner side. It is a server to server operation, authenticated by
        the partner client and addressed by an identifier the partner already holds, so it
        never depends on which NAU session happens to be open in a browser.

        The NAU user of a register is never changed here: a link is only ever established
        through the authenticated SSO flow, where the user proves who they are. Moving a
        link to a different NAU user means deleting it and linking again.

        Returns:
            dict: The updated SSO register.

        Example of payload:
        {
            "external_user_id": "external_user_123",
            "new_external_user_id": "external_user_456",
        }

        Or, addressing the register by its NAU user:
        {
            "username": "nau_user_123",
            "new_external_user_id": "external_user_456",
        }
        """
        described_as = None

        try:
            logger.info("PartnerSSOManagementView: PATCH request received.")

            client: PartnerAPIClient = request.partner_client
            if not client.is_active:
                logger.error("PartnerSSOManagementView: Inactive client attempted to access endpoint.")
                raise PartnerIntegrationInactiveClientException()

            new_external_user_id = request.data.get("new_external_user_id")
            lookup, described_as = self.build_register_lookup(
                client,
                external_user_id=request.data.get("external_user_id"),
                username=request.data.get("username"),
            )

            if not lookup:
                error_message = "An external user ID or a username must be provided to update an SSO register."
                logger.error(f"PartnerSSOManagementView: {error_message}")

                return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

            if not new_external_user_id:
                error_message = "A new external user ID must be provided to update an SSO register."
                logger.error(f"PartnerSSOManagementView: {error_message}")

                return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

            sso_register = SSOPartnerIntegration.objects.get(**lookup)

            if sso_register.external_user_id != new_external_user_id:
                sso_register.external_user_id = new_external_user_id
                try:
                    sso_register.save()
                except IntegrityError:
                    # The unique constraint on `(partner_client, external_user_id)` decides
                    # this, so a read beforehand would only repeat the same answer while
                    # leaving a window for a concurrent request to claim the identifier.
                    conflict_message = (
                        f"The external user ID '{new_external_user_id}' is already linked to another NAU user."
                    )
                    logger.error(f"PartnerSSOManagementView: {conflict_message}")

                    return Response({"error": conflict_message}, status=status.HTTP_409_CONFLICT)

            serializer = SSOUserSerializer(sso_register)

            return Response(serializer.data, status=status.HTTP_200_OK)
        except SSOPartnerIntegration.DoesNotExist:
            error_message = f"SSO register with {described_as} not found."
            logger.error(f"PartnerSSOManagementView: {error_message}")

            return Response({"error": error_message}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("PartnerSSOManagementView: Unexpected error.", exc_info=e)
            return Response(
                {"error": "An unexpected error occurred, please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request):
        """
        HTTP GET handler to retrieve SSO registers for the authenticated partner client.

        A register can be addressed by `external_user_id` or by the NAU `username`.
        """
        described_as = None

        try:
            logger.info("PartnerSSOManagementView: GET request received.")

            client: PartnerAPIClient = request.partner_client
            if not client.is_active:
                logger.error("PartnerSSOManagementView: Inactive client attempted to access endpoint.")
                raise PartnerIntegrationInactiveClientException()

            # By the current implementation, we require an identifier to retrieve SSO registers,
            # but it's clearly possible to exist scenarious where we want to retrieve all registers for
            # a given client. For this to work, oriented by necessity, we need to change this implementation
            # making this to consider more information beyond of only the single register identifiers.
            lookup, described_as = self.build_register_lookup(
                client,
                external_user_id=self.request.query_params.get("external_user_id"),
                username=self.request.query_params.get("username"),
            )

            if not lookup:
                error_message = "An external user ID or a username must be provided to retrieve SSO registers."
                logger.error(f"PartnerSSOManagementView: {error_message}")
                return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

            logger.info(f"PartnerSSOManagementView: Retrieving SSO register for {described_as}.")
            sso_register = SSOPartnerIntegration.objects.get(**lookup)
            serializer = SSOUserSerializer(sso_register)
            data = serializer.data

            return Response(data, status=status.HTTP_200_OK)
        except SSOPartnerIntegration.DoesNotExist:
            error_message = f"SSO register with {described_as} not found."
            logger.error(f"PartnerSSOManagementView: {error_message}")
            return Response({"error": error_message}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("PartnerSSOManagementView: Unexpected error.", exc_info=e)
            return Response(
                {"error": "An unexpected error occurred, please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
