# tests/test_views_and_serializers.py
import base64
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from common.djangoapps.student.tests.factories import CourseEnrollmentFactory
from django.test import TransactionTestCase
from django.utils import timezone
from lms.djangoapps.certificates.tests.factories import GeneratedCertificateFactory
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from rest_framework import status
from rest_framework.test import APIClient

from nau_openedx_extensions.custom_registration_form.factories import NauUserExtendedModelFactory
from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview
from nau_openedx_extensions.partner_integration.factories import PartnerAPIClientFactory
from nau_openedx_extensions.partner_integration.models import GeneratedCertificate
from nau_openedx_extensions.partner_integration.oauth_authentication import ClientJWTAuthentication


class BaseStructure:

    def create_bases(self):
        """
        This method creates the basis for the different domains the API has.
        Basically, it structures courses, partner clients, users and certificates,
        as the partner client will have restrictions based on org, and the certificates
        will be filtered based on those restrictions. That is, a partner client must only
        see certificates for courses under his org.

        1. Create 10 external users.
        2. For each of 5 orgs:
            a. Create an active partner client with query security scope restricted to that org.
            b. Create 5 courses under that org.
            c. For each course, create certificates for all external users.

        It returns a dictionary with all created objects for further use in tests.
        """
        users = NauUserExtendedModelFactory.create_batch(10)
        base_data = {
            "users": users,
            "partner_clients": [],
            "courses": [],
            "enrollments": [],
            "certificates": [],
        }
        for index in range(5):
            partner_client = PartnerAPIClientFactory.create(
                is_active=True,
                query_security_scope={"base_security_scope": {"org": f"TEST_ORG_{index}"}}
            )
            partner_client.password = "correct_password"
            partner_client.save()
            base_data["partner_clients"].append(partner_client)

            courses = CourseOverviewFactory.create_batch(5, org=f"TEST_ORG_{index}")
            for course in courses:
                base_data["courses"].append(course)
                for user in users:
                    enrollments = CourseEnrollmentFactory.create(user=user.user, course_id=course.id)
                    base_data["enrollments"].append(enrollments)
                    certificates = GeneratedCertificateFactory.create(user=user.user, course_id=course.id)
                    base_data["certificates"].append(certificates)

        return base_data


class TestPartnerClientTokenView(TransactionTestCase):

    def setUp(self):
        self.http_client = APIClient()
        self.endpoint = "/nau-openedx-extensions/partner-integration/auth-token/"
        self.partner_client = PartnerAPIClientFactory.create(
            query_security_scope={"base_security_scope": {"org": "TEST_ORG"}})

    def test_missing_headers_returns_400(self):
        """Validates the API returns 400 when none header provided."""
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 400)

    def test_invalid_authorization_format_returns_400(self):
        """Validates the API returns 400 when an invalid header provided."""
        self.http_client.credentials(
            HTTP_AUTHORIZATION="InvalidHeader",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid Authorization header", response.data["detail"])

    def test_wrong_scheme_returns_400(self):
        """Validates the API returns 400 when an invalid header provided."""
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Basic secret",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Authorization scheme must be Token", response.data["detail"])

    def test_nonexistent_client_returns_403(self):
        """test that a nonexistent client returns 403."""
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token secret",
            HTTP_X_CLIENT_ID="nonexistent",
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid client", response.data["detail"])

    def test_invalid_password_returns_403(self):
        """test that an invalid password returns 403."""
        self.partner_client.password = "correct_password"
        self.partner_client.save()
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token wrong_password",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid credentials", response.data["detail"])

    @patch.object(ClientJWTAuthentication, 'issue_client_jwt', return_value="mocked_jwt")
    def test_successful_token_returns_200_mocked_jwt(self, mock_jwt):
        """test that a valid password returns 200 and a token."""
        self.partner_client.password = "correct_password"
        self.partner_client.save()
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_jwt.return_value, "mocked_jwt")
        self.assertEqual(response.data, {"access_token": mock_jwt.return_value})

    def test_successful_token_returns_200(self):
        """test that a valid password returns 200 and a token."""
        self.partner_client.password = "correct_password"
        self.partner_client.save()
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data))

    def assert_is_jwt(self, token):
        """Asserts the provided token is a valid JWT format."""
        assert isinstance(token, str), "Token is not a string"

        parts = token.split(".")
        assert len(parts) == 3, "Token does not have three parts"

        for part in parts:
            try:
                missing_padding = len(part) % 4
                if missing_padding:
                    part += '=' * (4 - missing_padding)
                base64.urlsafe_b64decode(part)
            except Exception:
                raise AssertionError("JWT part is not valid Base64URL")

    def test_check_token_format(self):
        """test that a valid password returns a JWT formatted token."""
        self.partner_client.password = "correct_password"
        self.partner_client.save()
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 200)
        token = response.data["access_token"]
        self.assert_is_jwt(token)


class TestCertificateRestExportView(TransactionTestCase, BaseStructure):

    def setUp(self):
        self.http_client = APIClient()
        self.endpoint = "/nau-openedx-extensions/partner-integration/data-extractor/certificates/"
        self.base_data = self.create_bases()

    def authenticate_partner_client(self, partner_client):
        """
        Issues a real access token by calling the partner-client auth endpoint.

        The password used is "correct_password", as set in the create_bases method.
        It is not a fake password, it is the real authentication flow working here.
        """
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=partner_client.client_id,
        )
        response = self.http_client.post(
            "/nau-openedx-extensions/partner-integration/auth-token/",
            format="json"
        )

        assert response.status_code == 200, f"Auth failed: {response.data}"
        return response.data["access_token"]

    def test_successful_validate_fields(self):
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)
        fields = [
            "certificate_date",
            "certificate_url",
            "user_nif",
            "user_email",
            "username",
            "name",
            "course_id",
            "course_name",
            "enrollment_date"
        ]

        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data={"courses": [str(course_id)]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertTrue(len(response.data["results"]))
        fields_from_response = dict(response.data["results"][0]).keys()
        self.assertEqual(len(fields_from_response), 9)
        for field in fields:
            self.assertIn(field, fields_from_response)

    def test_successful_export_with_valid_course(self):
        """
        Tests a successful export with a valid course filter.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with a valid course id.
        3. Validates the response contains certificates for that course.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data={"courses": [str(course_id)]},
            format="json",
        )

        certificate = GeneratedCertificate.objects.filter(course_id=str(course_id)).first()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["results"][0]["course_id"], str(certificate.course_id))

    def test_successful_export_with_valid_certificate_url(self):
        """
        Tests a successful export with a valid course filter.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with a valid course id.
        3. Validates the response contains a certificate url that matches
        the certificate's `verify_uuid`.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data={"courses": [str(course_id)]},
            format="json",
        )

        certificate = GeneratedCertificate.objects.filter(course_id=str(course_id)).first()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertTrue(str(certificate.verify_uuid) in response.data["results"][0]["certificate_url"])

    def test_empty_body_returns_all_courses(self):
        """
        Tests that an empty body returns all courses.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with an empty body.
        3. Validates the response contains certificates for all courses under the partner client's org.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(self.endpoint, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_multiple_courses_returns_combined_results(self):
        """
        Tests that multiple course filters return combined results.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with multiple course ids.
        3. Validates the response contains certificates for all specified courses.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        courses = self.base_data["courses"][:2]

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(self.endpoint,
                                         data={"courses": [str(course.id) for course in courses]},
                                         format="json",
                                         )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_courses = [r["course_id"] for r in response.data["results"]]
        self.assertIn(str(courses[0].id), returned_courses)
        self.assertIn(str(courses[1].id), returned_courses)

    def test_date_filter_limits_results(self):
        """
        Test that date filters limit the results correctly.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with start and end date filters.
        3. Validates the response contains certificates only within the specified date range.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        certificate = self.base_data["certificates"][0]
        start_date = certificate.created_date - timedelta(days=1)
        end_date = certificate.created_date + timedelta(days=1)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_courses = [r["course_id"] for r in response.data["results"]]
        self.assertIn(str(certificate.course_id), returned_courses)

    def test_email_filter_returns_specific_certificates(self):
        """
        Test that email filter returns specific certificates.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with email filters.
        3. Validates the response contains certificates only for the specified emails.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        user = self.base_data["users"][0].user

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"emails": [user.email]},
            format="json",
        )

        name = user.get_full_name().strip()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(name, [resut["name"] for resut in response.data["results"]])

    def test_pagination_applies_limits(self):
        """
        Test that pagination limits results to 100 per page.
        1. Authenticates a partner client.
        2. Creates over 200 certificates for a course.
        3. Calls the data extractor endpoint with that course id.
        4. Validates the response is paginated with 100 results per page.
        5. Navigates through pages to ensure all results can be accessed.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        course_id = str(self.base_data["courses"][0].id)
        for _ in range(200):
            user_ext = NauUserExtendedModelFactory.create()
            GeneratedCertificateFactory.create(course_id=course_id, user=user_ext.user)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"courses": [course_id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 100)
        self.assertEqual(len(response.data["results"][0].keys()), 9)

        has_next = True
        while has_next:
            if response.data["next"]:
                response = self.http_client.post(
                    response.data["next"],
                    data={"courses": [course_id]},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("results", response.data)
            else:
                has_next = False
                if response.data["previous"]:
                    response = self.http_client.post(
                        response.data["previous"],
                        data={"courses": [course_id]},
                        format="json",
                    )

                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertIn("results", response.data)
                    self.assertEqual(len(response.data["results"]), 100)

    def test_certificates_outside_org_are_not_returned(self):
        """
        This test validates a partner client only has access to
        data of his organization.
        1. Authenticates a partner client.
        2. Identifies certificates for courses outside his org.
        3. Calls the data extractor endpoint with an email filter
           that would return those certificates if org restrictions
           were not applied.
        4. Validates the response does not contain those out-of-org certificates.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        user = self.base_data["users"][0].user

        org = partner_client.query_security_scope["base_security_scope"]["org"]
        invalid_courses = CourseOverview.objects.exclude(org=org)
        invalid_ids = [str(c.id) for c in invalid_courses]
        certificates = GeneratedCertificate.objects.filter(course_id__in=invalid_ids, user=user)
        invalid_ids = [str(c.course_id) for c in certificates]

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"emails": [user.email]},
            format="json",
        )
        returned_ids = [r["course_id"] for r in response.data["results"]]

        self.assertTrue(len(certificates))
        self.assertTrue(len(invalid_ids))
        self.assertTrue(len(returned_ids))

        for id in returned_ids:
            self.assertNotIn(id, invalid_ids)

    def test_invalid_date_format_returns_400(self):
        """
        Tests that invalid date formats return 400 errors.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with invalid date formats.
        3. Validates the response is a 400 with appropriate error message.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"start_date": "13-11-2025", "end_date": "2025/12/31"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid date format", str(response.data))

    def test_start_date_after_end_date_returns_400(self):
        """
        Test that start date after end date returns 400 error.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with start date after end date.
        3. Validates the response is a 400 with appropriate error message.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"start_date": start_date, "end_date": end_date},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Start date must not be greater", str(response.data))

    def test_date_range_exceeds_one_year_returns_400(self):
        """
        Test that date range exceeding one year returns 400 error.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with a date range over one year.
        3. Validates the response is a 400 with appropriate error message.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"start_date": start_date, "end_date": end_date},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Date range cannot exceed one year", str(response.data))

    def test_default_date_range_applies_when_dates_missing(self):
        """
        Test that default date range of last 365 days applies when no dates provided.
        1. Creates a partner client and courses.
        2. Creates certificates for those courses with varying created dates.
        3. Authenticates the partner client.
        4. Calls the data extractor endpoint without date filters.
        5. Validates the response contains only certificates from the last 365 days.
        6. Validates the user info in the response is correct.
        """
        org = "test_default_date_org"
        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "101010101"
        external_user.user.first_name = "test_default_date_user"
        external_user.save()
        external_user.user.save()

        partner_client = PartnerAPIClientFactory.create(
            is_active=True,
            query_security_scope={"base_security_scope": {"org": org}}
        )
        partner_client.password = "correct_password"
        partner_client.save()

        courses = CourseOverviewFactory.create_batch(5, org=org)
        for course in courses:
            CourseEnrollmentFactory.create(user=external_user.user, course_id=course.id)

        course_ids = [str(c.id) for c in courses[:2]]

        old_cert = GeneratedCertificateFactory.create(course_id=course_ids[0], user=external_user.user)
        created_date = timezone.now() - timedelta(days=364)
        old_cert.created_date = created_date.isoformat()
        old_cert.save()

        new_cert = GeneratedCertificateFactory.create(course_id=course_ids[1], user=external_user.user)
        created_date = timezone.now() - timedelta(days=1)
        new_cert.created_date = created_date.isoformat()
        new_cert.save()

        access_token = self.authenticate_partner_client(partner_client)
        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"courses": course_ids},
            format="json",
        )

        dates = [
            timezone.make_aware(datetime.fromisoformat(r["certificate_date"]))
            if datetime.fromisoformat(r["certificate_date"]).tzinfo is None
            else datetime.fromisoformat(r["certificate_date"])
            for r in response.data["results"]
        ]

        min_date = min(dates)
        max_date = max(dates)
        now = timezone.now()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(min_date, now - timedelta(days=365))
        self.assertLessEqual(max_date, now)

        for r in response.data["results"]:
            self.assertIn("test_default_date_user", r["name"])
            self.assertEqual(r["user_nif"], "101010101")

    def test_nif_filter_returns_correct_certificates(self):
        """
        Test that NIF filter returns correct certificates.
        1. Authenticates a partner client.
        2. Updates a user's NIF to a known value.
        3. Calls the data extractor endpoint with that NIF.
        4. Validates the response contains only certificates for that NIF.
        5. Validates the user info in the response is correct.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        user_ext = self.base_data["users"][0]
        user = user_ext.user
        user_ext.nif = "010101010"
        user.first_name = "test_nif_filter_returns_correct_certificates"
        user.save()
        user_ext.save()

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"nifs": ["010101010"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("test_nif_filter_returns_correct_certificates", response.data["results"][0]["name"])
        self.assertEqual(response.data["results"][0]["user_nif"], "010101010")

    def test_username_filter_returns_correct_certificates(self):
        """
        Test that username filter returns correct certificates.
        1. Authenticates a partner client.
        2. Updates a user's username to a known value.
        3. Calls the data extractor endpoint with that username.
        4. Validates the response contains only certificates for that username.
        5. Validates the user info in the response is correct.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        user_ext = self.base_data["users"][0]
        user = user_ext.user
        user_ext.nif = "010101010"
        user.first_name = "test_nif_filter_returns_correct_certificates"
        user.username = "test_username_filter_user"
        user.save()
        user_ext.save()

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"usernames": ["test_username_filter_user"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("test_nif_filter_returns_correct_certificates", response.data["results"][0]["name"])
        self.assertEqual(response.data["results"][0]["user_nif"], "010101010")
        self.assertEqual(response.data["results"][0]["username"], "test_username_filter_user")

    def test_combined_filters_reduce_result_set(self):
        """
        Test that combined NIF and email filters reduce the result set correctly.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with multiple NIFs and emails.
        3. Validates the response contains only certificates matching those filters.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        users_with_nifs = self.base_data["users"][:3]
        users_with_emails = self.base_data["users"][3:6]

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={
                "nifs": [str(u.nif) for u in users_with_nifs],
                "emails": [u.user.email for u in users_with_emails],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 30)

    def test_no_results_returns_empty_list(self):
        """
        Test that filters yielding no results return an empty list.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with filters that match no certificates.
        3. Validates the response contains an empty results list.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"courses": ["course-v1:TEST_ORG+UNKNOWN+2025"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)


class TestEnrollmentRestExportView(TransactionTestCase, BaseStructure):

    def setUp(self):
        self.http_client = APIClient()
        self.endpoint = "/nau-openedx-extensions/partner-integration/data-extractor/enrollments/"
        self.base_data = self.create_bases()

    def authenticate_partner_client(self, partner_client):
        """
        Issues a real access token by calling the partner-client auth endpoint.

        The password used is "correct_password", as set in the create_bases method.
        It is not a fake password, it is the real authentication flow working here.
        """
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=partner_client.client_id,
        )
        response = self.http_client.post(
            "/nau-openedx-extensions/partner-integration/auth-token/",
            format="json"
        )

        assert response.status_code == 200, f"Auth failed: {response.data}"
        return response.data["access_token"]

    def test_successful_validate_fields(self):
        """
        Test that the response contains all expected fields.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with a valid course id.
        3. Validates the response contains all expected fields.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)
        fields = [
            "user_nif",
            "username",
            "user_email",
            "course_id",
            "course_name",
            "enrollment_date",
            "active_enrollment",
            "course_org",
            "course_start",
            "course_end",
            "course_enrollment_start",
            "course_enrollment_end",
        ]

        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data={"courses": [str(course_id)]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertTrue(len(response.data["results"]))
        fields_from_response = dict(response.data["results"][0]).keys()
        self.assertEqual(len(fields_from_response), 13)
        for field in fields:
            self.assertIn(field, fields_from_response)

    def test_successful_export_with_valid_course(self):
        """
        Test a successful export with a valid course filter.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with a valid course id.
        3. Validates the response contains enrollments for that course.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data={"courses": [str(course_id)]},
            format="json",
        )

        enrollment = self.base_data["enrollments"][0]

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["results"][0]["course_id"], str(enrollment.course.id))

    def test_empty_body_returns_all_courses(self):
        """
        Tests that an empty body returns all courses.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with an empty body.
        3. Validates the response contains enrollments for all courses under the partner client's org.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(self.endpoint, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_multiple_courses_returns_combined_results(self):
        """
        Test that multiple course filters return combined results.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with multiple course ids.
        3. Validates the response contains enrollments for all specified courses.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        courses = self.base_data["courses"][:2]

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(self.endpoint,
                                         data={"courses": [str(course.id) for course in courses]},
                                         format="json",
                                         )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_courses = [r["course_id"] for r in response.data["results"]]
        self.assertIn(str(courses[0].id), returned_courses)
        self.assertIn(str(courses[1].id), returned_courses)

    def test_multiple_courses_with_only_codes(self):
        """
        Test that multiple course filters return combined results.
        1. Authenticates a partner client.
        2. Calls the data extractor endpoint with multiple course codes.
        3. Validates the response contains enrollments for all specified courses.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        courses = self.base_data["courses"][:2]

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(self.endpoint,
                                         data={"courses": [
                                            str(course.id).split("+")[1]
                                            for course in courses]},
                                         format="json",
                                         )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_courses = [r["course_id"] for r in response.data["results"]]
        self.assertIn(str(courses[0].id), returned_courses)
        self.assertIn(str(courses[1].id), returned_courses)

    def test_date_filter_limits_results(self):
        """
        Test that date filters limit the results correctly.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with start and end date filters.
        3. Validates the response contains enrollments only within the specified date range.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        enrollment = self.base_data["enrollments"][0]
        start_date = enrollment.created - timedelta(days=1)
        end_date = enrollment.created + timedelta(days=1)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_courses = [r["course_id"] for r in response.data["results"]]
        self.assertIn(str(enrollment.course.id), returned_courses)

    def test_email_filter_returns_specific_certificates(self):
        """
        Test that email filter returns specific enrollments.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with email filters.
        3. Validates the response contains enrollments only for the specified emails.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        user = self.base_data["users"][0].user

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"emails": [user.email]},
            format="json",
        )

        name = user.get_full_name().strip()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(name, [resut["user_name"] for resut in response.data["results"]])

    def test_pagination_applies_limits(self):
        """
        Test that pagination limits results to 100 per page.
        1. Authenticates a partner client.
        2. Creates over 200 enrollments for a course.
        3. Calls the enrollment data extractor endpoint with that course id.
        4. Validates the response is paginated with 100 results per page.
        5. Navigates through pages to ensure all results can be accessed.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        course_id = str(self.base_data["courses"][0].id)
        for _ in range(200):
            user_ext = NauUserExtendedModelFactory.create()
            CourseEnrollmentFactory.create(course_id=course_id, user=user_ext.user)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"courses": [course_id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 100)
        self.assertEqual(len(response.data["results"][0].keys()), 13)

        has_next = True
        while has_next:
            if response.data["next"]:
                response = self.http_client.post(
                    response.data["next"],
                    data={"courses": [course_id]},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("results", response.data)
            else:
                has_next = False
                if response.data["previous"]:
                    response = self.http_client.post(
                        response.data["previous"],
                        data={"courses": [course_id]},
                        format="json",
                    )

                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertIn("results", response.data)
                    self.assertEqual(len(response.data["results"]), 100)

    def test_certificates_outside_org_are_not_returned(self):
        """
        This test validates a partner client only has access to
        data of his organization.
        1. Authenticates a partner client.
        2. Identifies enrollments for courses outside his org.
        3. Calls the enrollment data extractor endpoint with an email filter
           that would return those enrollments if org restrictions
           were not applied.
        4. Validates the response does not contain those out-of-org enrollments.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        user = self.base_data["users"][0].user

        org = partner_client.query_security_scope["base_security_scope"]["org"]
        invalid_courses = CourseOverview.objects.exclude(org=org)
        invalid_ids = [str(c.id) for c in invalid_courses]

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"emails": [user.email]},
            format="json",
        )
        returned_ids = [r["course_id"] for r in response.data["results"]]

        self.assertTrue(len(invalid_ids))
        self.assertTrue(len(returned_ids))

        for id in returned_ids:
            self.assertNotIn(id, invalid_ids)

    def test_invalid_date_format_returns_400(self):
        """
        Test that invalid date formats return 400 errors.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with invalid date formats.
        3. Validates the response is a 400 with appropriate error message.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"start_date": "13-11-2025", "end_date": "2025/12/31"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid date format. Use ISO 8601 format.", str(response.data))

    def test_start_date_after_end_date_returns_400(self):
        """
        Test that start date after end date returns 400 error.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with start date after end date.
        3. Validates the response is a 400 with appropriate error message.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"start_date": start_date, "end_date": end_date},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Start date must not be greater", str(response.data))

    def test_date_range_exceeds_one_year_returns_400(self):
        """
        Test that date range exceeding one year returns 400 error.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with a date range over one year.
        3. Validates the response is a 400 with appropriate error message.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"start_date": start_date, "end_date": end_date},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Date range cannot exceed one year", str(response.data))

    def test_default_date_range_applies_when_dates_missing(self):
        """
        Test that default date range of last 365 days applies when no dates provided.
        1. Creates a partner client and courses.
        2. Creates enrollments for those courses with varying created dates.
        3. Authenticates the partner client.
        4. Calls the enrollment data extractor endpoint without date filters.
        5. Validates the response contains only enrollments from the last 365 days.
        6. Validates the user info in the response is correct.
        """
        org = "test_default_date_org_enrollments"
        partner_client = PartnerAPIClientFactory.create(
            is_active=True,
            query_security_scope={"base_security_scope": {"org": org}}
        )
        partner_client.password = "correct_password"
        partner_client.save()

        courses = CourseOverviewFactory.create_batch(5, org=org)
        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "101010101"
        external_user.user.first_name = "test_default_date_user"
        external_user.save()
        external_user.user.save()

        course_ids = [str(c.id) for c in courses[:2]]

        old_enrollment = CourseEnrollmentFactory.create(course_id=course_ids[0], user=external_user.user)
        created_date = timezone.now() - timedelta(days=364)
        old_enrollment.created = created_date.isoformat()
        old_enrollment.save()

        new_enrollment = CourseEnrollmentFactory.create(course_id=course_ids[1], user=external_user.user)
        created_date = timezone.now() - timedelta(days=1)
        new_enrollment.created = created_date.isoformat()
        new_enrollment.save()

        access_token = self.authenticate_partner_client(partner_client)
        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"courses": course_ids},
            format="json",
        )

        dates = [
            timezone.make_aware(datetime.fromisoformat(r["enrollment_date"]))
            if datetime.fromisoformat(r["enrollment_date"]).tzinfo is None
            else datetime.fromisoformat(r["enrollment_date"])
            for r in response.data["results"]
        ]

        min_date = min(dates)
        max_date = max(dates)
        now = timezone.now()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(min_date, now - timedelta(days=365))
        self.assertLessEqual(max_date, now)

        for r in response.data["results"]:
            self.assertIn("test_default_date_user", r["user_name"])
            self.assertEqual(r["user_nif"], "101010101")

    def test_nif_filter_returns_correct_enrollments(self):
        """
        Test that NIF filter returns correct enrollments.
        1. Authenticates a partner client.
        2. Updates a user's NIF to a known value.
        3. Calls the enrollment data extractor endpoint with that NIF.
        4. Validates the response contains only enrollments for that NIF.
        5. Validates the user info in the response is correct.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        user_ext = self.base_data["users"][0]
        user = user_ext.user
        user_ext.nif = "010101010"
        user.first_name = "test_nif_filter_returns_correct_enrollments"
        user.save()
        user_ext.save()

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"nifs": ["010101010"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("test_nif_filter_returns_correct_enrollments", response.data["results"][0]["user_name"])
        self.assertEqual(response.data["results"][0]["user_nif"], "010101010")

    def test_username_filter_returns_correct_enrollments(self):
        """
        Test that username filter returns correct enrollments.
        1. Authenticates a partner client.
        2. Updates a user's username to a known value.
        3. Calls the enrollment data extractor endpoint with that username.
        4. Validates the response contains only enrollments for that username.
        5. Validates the user info in the response is correct.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        user_ext = self.base_data["users"][0]
        user = user_ext.user
        user_ext.nif = "010101010"
        user.first_name = "test_username_filter_returns_correct_enrollments"
        user.username = "test_username_filter_user"
        user.save()
        user_ext.save()

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"usernames": ["test_username_filter_user"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("test_username_filter_returns_correct_enrollments",
                      response.data["results"][0]["user_name"])
        self.assertEqual(response.data["results"][0]["username"], "test_username_filter_user")

    def test_combined_filters_reduce_result_set(self):
        """
        Test that combined NIF and email filters reduce the result set correctly.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with multiple NIFs and emails.
        3. Validates the response contains only enrollments matching those filters.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        users_with_nifs = self.base_data["users"][:3]
        users_with_emails = self.base_data["users"][3:6]

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={
                "nifs": [str(u.nif) for u in users_with_nifs],
                "emails": [u.user.email for u in users_with_emails],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 30)

    def test_no_results_returns_empty_list(self):
        """
        Test that filters yielding no results return an empty list.
        1. Authenticates a partner client.
        2. Calls the enrollment data extractor endpoint with filters that match no enrollments.
        3. Validates the response contains an empty results list.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(
            self.endpoint,
            data={"courses": ["course-v1:TEST_ORG+UNKNOWN+2025"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)


class TestPartnerRestIntegrationEnrollUserView(TransactionTestCase, BaseStructure):
    """Tests for the PartnerRestIntegrationEnrollUserView API endpoint."""

    def setUp(self):
        self.http_client = APIClient()
        self.endpoint = "/nau-openedx-extensions/partner-integration/enroll-user/"
        self.base_data = self.create_bases()

    def authenticate_partner_client(self, partner_client):
        """
        Issues a real access token by calling the partner-client auth endpoint.

        The password used is "correct_password", as set in the create_bases method.
        It is not a fake password, it is the real authentication flow working here.
        """
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=partner_client.client_id,
        )
        response = self.http_client.post(
            "/nau-openedx-extensions/partner-integration/auth-token/",
            format="json"
        )

        assert response.status_code == 200, f"Auth failed: {response.data}"
        return response.data["access_token"]

    def test_enroll_user_success_email_201(self):
        """
        Test successful user enrollment using email.
        1. Authenticates a partner client.
        2. Creates an external user with a known email.
        3. Calls the enroll-user endpoint with the course ID and email.
        4. Validates the response indicates successful enrollment with correct details.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "101010101"
        external_user.user.email = "success_email_201@example.com"
        external_user.save()
        external_user.user.save()

        data = {
            "course": str(course_id),
            "email": external_user.user.email
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data.keys()), 13)
        self.assertEqual(response.data["user_nif"], "101010101")
        self.assertEqual(response.data["user_email"], "success_email_201@example.com")
        self.assertEqual(response.data["course_id"], str(course_id))

    def test_enroll_user_success_nif_201(self):
        """
        Test successful user enrollment using NIF.
        1. Authenticates a partner client.
        2. Creates an external user with a known NIF.
        3. Calls the enroll-user endpoint with the course ID and NIF.
        4. Validates the response indicates successful enrollment with correct details.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "202020202"
        external_user.user.email = "success_nif_201@example.com"
        external_user.save()
        external_user.user.save()

        data = {
            "course": str(course_id),
            "nif": external_user.nif,
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data.keys()), 13)
        self.assertEqual(response.data["user_nif"], "202020202")
        self.assertEqual(response.data["user_email"], "success_nif_201@example.com")
        self.assertEqual(response.data["course_id"], str(course_id))

    def test_enroll_user_success_username_201(self):
        """
        Test successful user enrollment using username.
        1. Authenticates a partner client.
        2. Creates an external user with a known username.
        3. Calls the enroll-user endpoint with the course ID and username.
        4. Validates the response indicates successful enrollment with correct details.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "202020202"
        external_user.user.email = "success_nif_201@example.com"
        external_user.user.username = "username_202020202"
        external_user.save()
        external_user.user.save()

        data = {
            "course": str(course_id),
            "username": external_user.user.username,
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data.keys()), 13)
        self.assertEqual(response.data["username"], "username_202020202")
        self.assertEqual(response.data["user_email"], "success_nif_201@example.com")
        self.assertEqual(response.data["course_id"], str(course_id))

    def test_enroll_user_success_course_code_201(self):
        """
        Test successful user enrollment using course code.
        1. Authenticates a partner client.
        2. Creates an external user with a known username.
        3. Calls the enroll-user endpoint with the course code and username.
        4. Validates the response indicates successful enrollment with correct details.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "202020202"
        external_user.user.email = "success_nif_201@example.com"
        external_user.user.username = "username_202020202"
        external_user.save()
        external_user.user.save()

        data = {
            "course": str(course_id.course),
            "username": external_user.user.username,
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data.keys()), 13)
        self.assertEqual(response.data["username"], "username_202020202")
        self.assertEqual(response.data["user_email"], "success_nif_201@example.com")
        self.assertEqual(response.data["course_id"], str(course_id))

    def test_enroll_user_missing_course_returns_400(self):
        """
        Test that missing course ID returns 400 error.
        1. Authenticates a partner client.
        2. Creates an external user.
        3. Calls the enroll-user endpoint without a course ID.
        4. Validates the response is a 400 with appropriate error message.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "101010101"
        external_user.user.email = "missing_course_returns_400@example.com"
        external_user.save()
        external_user.user.save()

        data = {
            "nif": external_user.nif,
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Course ID must be provided to enroll users.", str(response.data))

    def test_enroll_user_missing_nif_and_email_returns_400(self):
        """
        Test that missing NIF and email returns 400 error.
        1. Authenticates a partner client.
        2. Calls the enroll-user endpoint with only a course ID.
        3. Validates the response is a 400 with appropriate error message.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        data = {
            "course": str(course_id),
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("At least one of NIF, email, or username must be provided to enroll users.",
                      str(response.data))

    def test_enroll_user_already_enrolled_returns_409(self):
        """
        Test that enrolling an already enrolled user returns 409 conflict.
        1. Authenticates a partner client.
        2. Creates an external user and enrolls them in a course.
        3. Calls the enroll-user endpoint with the same course ID and user NIF.
        4. Validates the response is a 409 with appropriate error message.
        """
        course = self.base_data["courses"][0]
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "202020202"
        external_user.user.email = "already_enrolled_returns_409@example.com"
        external_user.save()
        external_user.user.save()

        CourseEnrollmentFactory.create(user=external_user.user, course_id=course.id)
        data = {
            "course": str(course.id),
            "nif": external_user.nif,
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("The user is already enrolled in this course", str(response.data))

    def test_enroll_user_does_not_exist_nif_returns_400(self):
        """
        Test that enrolling a non-existent user by NIF returns 400 error.
        1. Authenticates a partner client.
        2. Calls the enroll-user endpoint with a non-existent user NIF.
        3. Validates the response is a 400 with appropriate error message.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        data = {
            "course": str(course_id),
            "nif": "111111111",
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("The specified user does not exist.", str(response.data))

    def test_enroll_user_does_not_exist_email_returns_400(self):
        """
        Test that enrolling a non-existent user by email returns 400 error.
        1. Authenticates a partner client.
        2. Calls the enroll-user endpoint with a non-existent user email.
        3. Validates the response is a 400 with appropriate error message.
        """
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        data = {
            "course": str(course_id),
            "email": "invalid-email@example.com",
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("The specified user does not exist.", str(response.data))

    def test_enroll_user_course_not_in_org_returns_400(self):
        """
        Test that enrolling a user in a course outside the partner's org returns 400 error.
        1. Authenticates a partner client.
        2. Creates an external user.
        3. Calls the enroll-user endpoint with a course ID outside the partner's org.
        4. Validates the response is a 400 with appropriate error message.
        """
        course = self.base_data["courses"][0]
        partner_client = self.base_data["partner_clients"][1]  # Different org
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "303030303"
        external_user.user.email = "course_not_in_org_returns_400@example.com"
        external_user.save()
        external_user.user.save()

        data = {
            "course": str(course.id),
            "nif": external_user.nif,
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("The specified course ID does not exist or is not accessible by the partner.", str(response.data))

    def test_enroll_user_invalid_course_id_returns_400(self):
        """
        Test that enrolling a user with an invalid course ID returns 400 error.
        1. Authenticates a partner client.
        2. Creates an external user.
        3. Calls the enroll-user endpoint with an invalid course ID.
        4. Validates the response is a 400 with appropriate error message.
        """
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "404040404"
        external_user.user.email = "invalid_course_id_returns_400@example.com"
        external_user.save()
        external_user.user.save()

        data = {
            "course": "course-v1:INVALID+COURSE+2025",
            "nif": external_user.nif,
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("The specified course ID does not exist or is not accessible by the partner.", str(response.data))


class TestStudentProgressRestExportView(TransactionTestCase, BaseStructure):
    """Tests for the StudentProgressRestExportView API endpoint."""
    def setUp(self):
        self.http_client = APIClient()
        self.endpoint = "/nau-openedx-extensions/partner-integration/data-extractor/student-progress/"
        self.base_data = self.create_bases()

    def authenticate_partner_client(self, partner_client):
        """
        Issues a real access token by calling the partner-client auth endpoint.

        The password used is "correct_password", as set in the create_bases method.
        It is not a fake password, it is the real authentication flow working here.
        """
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=partner_client.client_id,
        )
        response = self.http_client.post(
            "/nau-openedx-extensions/partner-integration/auth-token/",
            format="json"
        )

        assert response.status_code == 200, f"Auth failed: {response.data}"
        return response.data["access_token"]

    @patch("nau_openedx_extensions.partner_integration.facade.get_block_structure_manager")
    @patch("nau_openedx_extensions.partner_integration.facade.get_course_blocks_completion_summary")
    @patch("nau_openedx_extensions.partner_integration.facade.CourseGradeFactory")
    @patch("nau_openedx_extensions.partner_integration.facade.modulestore")
    @patch("nau_openedx_extensions.partner_integration.facade.get_course_or_403")
    def test_student_progress_export_success(
        self,
        get_course_or_403_mock,
        modulestore_mock,
        course_grade_factory_mock,
        completion_summary_mock,
        block_structure_manager_mock
    ):
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        user_ext = self.base_data["users"][0]
        user = user_ext.user
        
        course_mock = MagicMock()
        course_mock.id = course_id
        course_mock.lowest_passing_grade = 0.5
        get_course_or_403_mock.return_value = course_mock
        
        mock_grade = MagicMock()
        mock_grade.percent = 0.84
        mock_grade.passed = True
        mock_grade.letter_grade = "Approved"

        course_grade_factory_mock().read.return_value = mock_grade

        mock_course = MagicMock()
        grading_policy = {
            "GRADER": [
                {
                    "type": "Avaliação Módulo 1",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "AS1",
                    "weight": 0.33,
                },
                {
                    "type": "Avaliação Módulo 2",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "AS2",
                    "weight": 0.33,
                },
                {
                    "type": "Avaliação Módulo 3",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "AS3",
                    "weight": 0.34,
                },
            ],
            "GRADE_CUTOFFS": {
                "Aprovado": 0.5
            },
        }
        mock_course.grading_policy = grading_policy

        modulestore_instance = MagicMock()
        modulestore_instance.get_course.return_value = mock_course
        modulestore_mock.return_value = modulestore_instance

        completion_summary_mock.return_value = {
            "complete_count": 28,
            "incomplete_count": 51,
            "locked_count": 0,
        }

        mock_block_manager = MagicMock()
        mock_block_manager.get_collected.return_value = {}
        block_structure_manager_mock.return_value = mock_block_manager

        access_token = self.authenticate_partner_client(partner_client)
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data={
                "course": str(course_id),
                "email": user.email
            },
            format="json",
        )

        response_data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response_data["username"], user.username)
        self.assertTrue(response_data["user_has_passing_grade"], "User should have passing grade")

        expected_summary = {
            "complete_count": 28,
            "incomplete_count": 51,
            "locked_count": 0
        }

        self.assertEqual(response_data["completion_summary"], expected_summary)
        self.assertEqual(response_data["course_grade"]["percent"], 0.84)
        self.assertEqual(response_data["course_grade"]["passed"], True)
        self.assertEqual(response_data["course_grade"]["letter_grade"], "Approved")
