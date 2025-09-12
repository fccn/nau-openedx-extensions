# tests/test_views_and_serializers.py
import base64
from datetime import datetime, timedelta
from unittest.mock import patch

from common.djangoapps.student.tests.factories import CourseEnrollmentFactory
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from lms.djangoapps.certificates.tests.factories import GeneratedCertificateFactory
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from rest_framework import status
from rest_framework.test import APIClient

from nau_openedx_extensions.custom_registration_form.factories import NauUserExtendedModelFactory
from nau_openedx_extensions.partner_integration.factories import PartnerAPIClientFactory
from nau_openedx_extensions.partner_integration.models import GeneratedCertificate
from nau_openedx_extensions.partner_integration.oauth_authentication import ClientJWTAuthentication
from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview


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
            partner_client.set_password("correct_password")
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


@override_settings(
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            'NAME': ":memory:",
        }
    }
)
class TestPartnerClientTokenView(TransactionTestCase):

    def setUp(self):
        self.http_client = APIClient()
        self.endpoint = "/nau-openedx-extensions/partner-integration/auth-token/"
        self.partner_client = PartnerAPIClientFactory.create(
            query_security_scope={"base_security_scope": {"org": "TEST_ORG"}})

    def test_incorrect_endpoint_404(self):
        """
        Validates the API returns 404 when none endpoint is incorrect.
        It also validates all the tests find the API, as they are using
        the correct endpoint.
        """
        self.http_client.credentials(**{})
        response = self.http_client.post("incorrect_part")
        self.assertEqual(response.status_code, 404)

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
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token secret",
            HTTP_X_CLIENT_ID="nonexistent",
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertIn("Invalid client", response.data["detail"])

    def test_invalid_password_returns_403(self):
        self.partner_client.set_password("correct_password")
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
        self.partner_client.set_password("correct_password")
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
        self.partner_client.set_password("correct_password")
        self.partner_client.save()
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data))

    def assert_is_jwt(self, token):
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
        self.partner_client.set_password("correct_password")
        self.partner_client.save()
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token correct_password",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.endpoint, format="json")
        self.assertEqual(response.status_code, 200)
        token = response.data["access_token"]
        self.assert_is_jwt(token)


@override_settings(
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
)
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

    def test_empty_body_returns_all_courses(self):
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        self.http_client.credentials(**{"HTTP_AUTHORIZATION": f"Bearer {access_token}"})
        response = self.http_client.post(self.endpoint, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_multiple_courses_returns_combined_results(self):
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
        partner_client.set_password("correct_password")
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

    def test_combined_filters_reduce_result_set(self):
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


@override_settings(
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
)
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

    def test_enroll_user_success(self):
        course_id = self.base_data["courses"][0].id
        partner_client = self.base_data["partner_clients"][0]
        access_token = self.authenticate_partner_client(partner_client)

        external_user = NauUserExtendedModelFactory.create()
        external_user.nif = "101010101"
        external_user.user.email = "test_default_date_user@example.com"
        external_user.save()
        external_user.user.save()
        
        data = {
            "course": str(course_id),
            "emails": [
                external_user.user.email
            ]
        }
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.http_client.post(
            self.endpoint,
            data=data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(len(response.data[0].keys()), 14)
        self.assertEqual(response.data[0]["user_nif"], "101010101")
        self.assertEqual(response.data[0]["user_email"], "test_default_date_user@example.com")
        self.assertEqual(response.data[0]["course_id"], str(course_id))
        


