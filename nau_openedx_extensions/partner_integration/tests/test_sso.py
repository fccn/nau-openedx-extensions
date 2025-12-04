import logging

from common.djangoapps.student.tests.factories import UserFactory
from django.test import TransactionTestCase
from oauth2_provider.models import get_application_model
from rest_framework.test import APIClient

from nau_openedx_extensions.partner_integration.factories import PartnerAPIClientFactory, SSOPartnerIntegrationFactory
from nau_openedx_extensions.partner_integration.models import SSOPartnerIntegration

Application = get_application_model()

logger = logging.getLogger(__name__)


class TestCustomAuthorizationView(TransactionTestCase):

    def setUp(self):
        self.http_client = APIClient()
        self.endpoint = "/nau-openedx-extensions/partner-integration/sso/authorize/"

        self.partner_client = PartnerAPIClientFactory.create(
            is_active=True,
            query_security_scope={"base_security_scope": {"org": f"TEST_ORG"}}
        )
        self.partner_client.password = "correct_password"
        self.partner_client.save()

        self.app = Application.objects.create(
            name=self.partner_client.name,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://example.com/auth/callback",
        )
        self.jwt_token = self.authenticate_partner_client(self.partner_client)

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

    def build_oauth_url(self, jwt_token=None, client_id=None, external_user_id=None, redirect_uri=None):
        """Creates the oauth url according to the expected parameters"""
        if not jwt_token:
            jwt_token = self.jwt_token

        if not client_id:
            client_id = self.app.client_id

        url = (
            f"{self.endpoint}"
            f"?client_id={client_id}"
            f"&external_user_id={external_user_id}"
            f"&jwt_token={jwt_token}"
        )

        if redirect_uri:
            url = f"{url}&redirect_uri={redirect_uri}"

        return url

    def test_sso_redirect_login_page_success(self):
        """
        Validates the sso process redirects to login page
        when a sso register does not exist.
        """
        url = self.build_oauth_url(external_user_id="123456789")
        response = self.http_client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(str(response.url).startswith("/login?next="))
        self.assertTrue(
            "next=/nau-openedx-extensions/partner-integration/sso/authorize/" in str(response.url))

    def test_sso_auth_redirect_sso_callback_success(self):
        """
        Validates the sso process redirects to the client callback
        redirect uri after authenticate and create the sso register.
        """
        url = self.build_oauth_url(external_user_id="123456789")
        user = UserFactory.create(username='userexample', password='correct_password')

        logged_in = self.client.login(username="userexample", password="correct_password")
        self.assertTrue(logged_in)

        response = self.client.get(url)

        sso_register = SSOPartnerIntegration.objects.get(external_user_id="123456789")
        self.assertIsNotNone(sso_register)
        self.assertEqual(sso_register.partner_client.client_id, self.partner_client.client_id)
        self.assertEqual(sso_register.user.email, user.email)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(str(response.url).startswith("https://example.com/auth/callback"))
        self.assertTrue(user.email in str(response.url))

    def test_sso_updates_external_id(self):
        """
        Validates the sso process updates the `external_user_id`
        parameter when an existing user just logged in.
        """
        url = self.build_oauth_url(external_user_id="987654321")
        user = UserFactory.create(username='userexample', password='correct_password')
        SSOPartnerIntegrationFactory.create(
            user=user, partner_client=self.partner_client, external_user_id="123456789")

        self.assertTrue(SSOPartnerIntegration.objects.filter(external_user_id="123456789").exists())

        logged_in = self.client.login(username="userexample", password="correct_password")
        self.assertTrue(logged_in)

        response = self.client.get(url)

        self.assertFalse(SSOPartnerIntegration.objects.filter(external_user_id="123456789").exists())

        sso_register = SSOPartnerIntegration.objects.get(external_user_id="987654321")
        self.assertIsNotNone(sso_register)
        self.assertEqual(sso_register.partner_client.client_id, self.partner_client.client_id)
        self.assertEqual(sso_register.user.email, user.email)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(str(response.url).startswith("https://example.com/auth/callback"))
        self.assertTrue(user.email in str(response.url))

    def test_sso_auth_redirect_success_nau_page(self):
        url = self.build_oauth_url(external_user_id="123456789", redirect_uri="https://nau.edu.pt")
        user = UserFactory.create(username='userexample', password='correct_password')
        SSOPartnerIntegrationFactory.create(
            user=user, partner_client=self.partner_client, external_user_id="123456789")

        logged_in = self.client.login(username="userexample", password="correct_password")
        self.assertTrue(logged_in)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://nau.edu.pt")

    def test_sso_auth_redirects_to_default_link(self):
        url = self.build_oauth_url(external_user_id="123456789")
        user = UserFactory.create(username='userexample', password='correct_password')
        SSOPartnerIntegrationFactory.create(
            user=user, partner_client=self.partner_client, external_user_id="123456789")

        logged_in = self.client.login(username="userexample", password="correct_password")
        self.assertTrue(logged_in)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(str(response.url).startswith("https://example.com/auth/callback"))
        self.assertTrue(user.email in str(response.url))

    def test_sso_invalid_JWT_token_redirects_to_nau(self):
        url = self.build_oauth_url(external_user_id="123456789", jwt_token="invalid")
        user = UserFactory.create(username='userexample', password='correct_password')
        SSOPartnerIntegrationFactory.create(
            user=user, partner_client=self.partner_client, external_user_id="123456789")

        logged_in = self.client.login(username="userexample", password="correct_password")
        self.assertTrue(logged_in)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://www.nau.edu.pt")

    def test_sso_invalid_client_id_redirects_to_nau(self):
        url = self.build_oauth_url(external_user_id="123456789", client_id="invalid")
        user = UserFactory.create(username='userexample', password='correct_password')
        SSOPartnerIntegrationFactory.create(
            user=user, partner_client=self.partner_client, external_user_id="123456789")

        logged_in = self.client.login(username="userexample", password="correct_password")
        self.assertTrue(logged_in)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://www.nau.edu.pt")
