"""
Tests that harden the partner SSO flow, complementing `test_sso.py`.

They cover what was left open by https://github.com/fccn/nau-technical/issues/975:
authentication failures and tenant isolation of `PartnerSSOManagementView`, the lookup
by `username`, the unlink and relink support scenario, the remaining paths of
`CustomAuthorizationView` and the presence of the SSO constraints in the migrations.
"""
from common.djangoapps.student.tests.factories import UserFactory
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase, TransactionTestCase, override_settings
from oauth2_provider.models import get_application_model
from rest_framework.test import APIClient

from nau_openedx_extensions.partner_integration.factories import PartnerAPIClientFactory, SSOPartnerIntegrationFactory
from nau_openedx_extensions.partner_integration.models import SSOPartnerIntegration
from nau_openedx_extensions.partner_integration.serializers import SSOUserSerializer

Application = get_application_model()

AUTH_TOKEN_ENDPOINT = "/nau-openedx-extensions/partner-integration/auth-token/"
MANAGE_ENDPOINT = "/nau-openedx-extensions/partner-integration/sso/manage/"
AUTHORIZE_ENDPOINT = "/nau-openedx-extensions/partner-integration/sso/authorize/"
DEFAULT_NAU_URI = "https://www.nau.edu.pt"
CALLBACK_URI = "https://example.com/auth/callback"
PARTNER_SECRET = "correct_password"


def create_partner_client(**kwargs):
    """Creates an active partner client able to authenticate with `PARTNER_SECRET`."""
    partner_client = PartnerAPIClientFactory.create(
        is_active=True,
        query_security_scope={"base_security_scope": {"org": "TEST_ORG"}},
        **kwargs,
    )
    partner_client.password = PARTNER_SECRET
    partner_client.save()

    return partner_client


def issue_token(partner_client):
    """Issues a real access token through the partner client authentication endpoint."""
    http_client = APIClient()
    http_client.credentials(
        HTTP_AUTHORIZATION=f"Token {PARTNER_SECRET}",
        HTTP_X_CLIENT_ID=partner_client.client_id,
    )
    response = http_client.post(AUTH_TOKEN_ENDPOINT, format="json")
    assert response.status_code == 200, f"Auth failed: {response.data}"

    return response.data["access_token"]


class SSOManagementTestCase(TransactionTestCase):
    """Base of the `PartnerSSOManagementView` tests, with two partner clients."""

    def setUp(self):
        self.partner_client = create_partner_client()
        self.other_partner_client = create_partner_client()
        self.jwt_token = issue_token(self.partner_client)
        self.other_jwt_token = issue_token(self.other_partner_client)

    def api(self, jwt_token=None, **headers):
        """Returns an API client authenticated with the given token, the first partner's by default."""
        http_client = APIClient()
        http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_token or self.jwt_token}", **headers)

        return http_client

    def request_every_method(self, http_client, **data):
        """Executes the three operations of the endpoint, returning the responses by method."""
        return {
            "GET": http_client.get(MANAGE_ENDPOINT, data),
            "PATCH": http_client.patch(
                MANAGE_ENDPOINT, {**data, "new_external_user_id": "renamed"}, format="json"),
            "DELETE": http_client.delete(MANAGE_ENDPOINT, data, format="json"),
        }

    def assert_register_untouched(self, sso_register):
        """Asserts the register still exists with the same owner and external identification."""
        current = SSOPartnerIntegration.objects.get(id=sso_register.id)
        self.assertEqual(current.external_user_id, sso_register.external_user_id)
        self.assertEqual(current.user_id, sso_register.user_id)
        self.assertEqual(current.partner_client_id, sso_register.partner_client_id)


class TestSSOManagementAuthentication(SSOManagementTestCase):
    """The management endpoint only answers to an active and correctly authenticated partner client."""

    def setUp(self):
        super().setUp()
        self.sso_register = SSOPartnerIntegrationFactory.create(
            partner_client=self.partner_client, external_user_id="123456789")

    def assert_every_method_is_refused(self, http_client):
        """Asserts no operation is executed neither any data is returned."""
        for method, response in self.request_every_method(http_client, external_user_id="123456789").items():
            self.assertEqual(response.status_code, 401, method)
            self.assertNotIn("external_user_id", response.data, method)
            self.assertNotIn("success", response.data, method)

        self.assert_register_untouched(self.sso_register)

    def test_request_without_token_is_refused(self):
        self.assert_every_method_is_refused(APIClient())

    def test_request_with_invalid_token_is_refused(self):
        self.assert_every_method_is_refused(self.api(jwt_token="invalid"))

    def test_request_with_tampered_token_is_refused(self):
        header, payload, signature = self.jwt_token.split(".")
        tampered_signature = signature[:-2] + ("AA" if not signature.endswith("AA") else "BB")

        self.assert_every_method_is_refused(self.api(jwt_token=f"{header}.{payload}.{tampered_signature}"))

    def test_request_with_expired_token_is_refused(self):
        with override_settings(JWT_PARTNER_CLIENT_EXPIRATION=-60):
            expired_token = issue_token(self.partner_client)

        self.assert_every_method_is_refused(self.api(jwt_token=expired_token))

    def test_request_with_wrong_authorization_scheme_is_refused(self):
        """
        The token is only accepted as a `Bearer` one, the `Token` scheme is reserved to
        the secret used to issue it.
        """
        http_client = APIClient()
        http_client.credentials(HTTP_AUTHORIZATION=f"Token {self.jwt_token}")
        self.assert_every_method_is_refused(http_client)

        http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {PARTNER_SECRET}")
        self.assert_every_method_is_refused(http_client)

    def test_client_deactivated_after_issuing_the_token_is_refused(self):
        """
        A token issued while the partner client was active stops working as soon as the
        client is deactivated, it does not live until its expiration.
        """
        self.partner_client.is_active = False
        self.partner_client.save()

        self.assert_every_method_is_refused(self.api())

    def test_inactive_client_is_not_able_to_issue_a_token(self):
        self.partner_client.is_active = False
        self.partner_client.save()

        http_client = APIClient()
        http_client.credentials(
            HTTP_AUTHORIZATION=f"Token {PARTNER_SECRET}",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = http_client.post(AUTH_TOKEN_ENDPOINT, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("access_token", response.data)

    def test_reactivated_client_recovers_its_access(self):
        self.partner_client.is_active = False
        self.partner_client.save()
        self.assertEqual(self.api().get(MANAGE_ENDPOINT, {"external_user_id": "123456789"}).status_code, 401)

        self.partner_client.is_active = True
        self.partner_client.save()
        response = self.api().get(MANAGE_ENDPOINT, {"external_user_id": "123456789"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["external_user_id"], "123456789")

    def test_only_get_patch_and_delete_are_allowed(self):
        for method in ["post", "put"]:
            response = getattr(self.api(), method)(
                MANAGE_ENDPOINT, {"external_user_id": "123456789"}, format="json")

            self.assertEqual(response.status_code, 405, method)

        self.assert_register_untouched(self.sso_register)


class TestSSOManagementIsolation(SSOManagementTestCase):
    """A partner client only reaches its own SSO registers, whatever identifier it sends."""

    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(username="first_user", email="first_user@example.com")
        self.other_user = UserFactory.create(username="other_user", email="other_user@example.com")
        # The same external identification exists in both partner clients, for different NAU users.
        self.sso_register = SSOPartnerIntegrationFactory.create(
            partner_client=self.partner_client, user=self.user, external_user_id="shared-id")
        self.other_sso_register = SSOPartnerIntegrationFactory.create(
            partner_client=self.other_partner_client, user=self.other_user, external_user_id="shared-id")
        # A register that only exists for the other partner client.
        self.other_only_sso_register = SSOPartnerIntegrationFactory.create(
            partner_client=self.other_partner_client, external_user_id="other-only-id")

    def test_get_returns_the_register_of_the_authenticated_client(self):
        response = self.api().get(MANAGE_ENDPOINT, {"external_user_id": "shared-id"})
        other_response = self.api(self.other_jwt_token).get(MANAGE_ENDPOINT, {"external_user_id": "shared-id"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "first_user")
        self.assertEqual(other_response.status_code, 200)
        self.assertEqual(other_response.data["username"], "other_user")

    def test_response_exposes_only_the_documented_fields(self):
        """The partners rely on this contract, it must not gain neither lose fields unnoticed."""
        expected = {"external_user_id": "shared-id", "username": "first_user", "email": "first_user@example.com"}

        response = self.api().get(MANAGE_ENDPOINT, {"external_user_id": "shared-id"})
        self.assertEqual(dict(response.data), expected)

        response = self.api().patch(
            MANAGE_ENDPOINT, {"external_user_id": "shared-id", "new_external_user_id": "new-id"}, format="json")
        self.assertEqual(dict(response.data), {**expected, "external_user_id": "new-id"})

    def test_register_of_another_client_is_not_found_by_external_user_id(self):
        for method, response in self.request_every_method(self.api(), external_user_id="other-only-id").items():
            self.assertEqual(response.status_code, 404, method)
            self.assertNotIn(self.other_only_sso_register.user.username, str(response.data), method)
            self.assertNotIn(self.other_only_sso_register.user.email, str(response.data), method)

        self.assert_register_untouched(self.other_only_sso_register)

    def test_register_of_another_client_is_not_found_by_username(self):
        username = self.other_only_sso_register.user.username

        for method, response in self.request_every_method(self.api(), username=username).items():
            self.assertEqual(response.status_code, 404, method)
            self.assertNotIn(self.other_only_sso_register.external_user_id, str(response.data), method)
            self.assertNotIn(self.other_only_sso_register.user.email, str(response.data), method)

        self.assert_register_untouched(self.other_only_sso_register)

    def test_unknown_username_is_not_found(self):
        for method, response in self.request_every_method(self.api(), username="nobody").items():
            self.assertEqual(response.status_code, 404, method)

        self.assertEqual(SSOPartnerIntegration.objects.count(), 3)

    def test_delete_removes_only_the_register_of_the_authenticated_client(self):
        response = self.api().delete(MANAGE_ENDPOINT, {"external_user_id": "shared-id"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SSOPartnerIntegration.objects.filter(id=self.sso_register.id).exists())
        self.assert_register_untouched(self.other_sso_register)

    def test_delete_twice_answers_not_found_the_second_time(self):
        first = self.api().delete(MANAGE_ENDPOINT, {"external_user_id": "shared-id"}, format="json")
        second = self.api().delete(MANAGE_ENDPOINT, {"external_user_id": "shared-id"}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 404)
        self.assert_register_untouched(self.other_sso_register)

    def test_patch_renames_only_the_register_of_the_authenticated_client(self):
        response = self.api().patch(
            MANAGE_ENDPOINT, {"external_user_id": "shared-id", "new_external_user_id": "renamed-id"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.sso_register.refresh_from_db()
        self.assertEqual(self.sso_register.external_user_id, "renamed-id")
        self.assertEqual(self.sso_register.user, self.user)
        self.assert_register_untouched(self.other_sso_register)

    def test_patch_accepts_an_external_user_id_used_by_another_client(self):
        """The external identification is unique per partner client, not across them."""
        response = self.api().patch(
            MANAGE_ENDPOINT, {"external_user_id": "shared-id", "new_external_user_id": "other-only-id"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.sso_register.refresh_from_db()
        self.assertEqual(self.sso_register.external_user_id, "other-only-id")
        self.assert_register_untouched(self.other_only_sso_register)

    def test_client_id_header_of_another_client_does_not_change_the_tenant(self):
        """The partner client comes from the token alone, a header is not able to impersonate another one."""
        http_client = self.api(HTTP_X_CLIENT_ID=str(self.other_partner_client.client_id))

        response = http_client.get(MANAGE_ENDPOINT, {"external_user_id": "shared-id"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "first_user")

        response = http_client.get(MANAGE_ENDPOINT, {"external_user_id": "other-only-id"})
        self.assertEqual(response.status_code, 404)

    def test_external_user_id_and_username_together_must_match_the_same_register(self):
        """When both identifiers are sent they are combined, none of them takes precedence."""
        matching = {"external_user_id": "shared-id", "username": "first_user"}
        mismatching = {"external_user_id": "shared-id", "username": "other_user"}

        response = self.api().get(MANAGE_ENDPOINT, matching)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "first_user")

        for method, response in self.request_every_method(self.api(), **mismatching).items():
            self.assertEqual(response.status_code, 404, method)
        self.assert_register_untouched(self.sso_register)
        self.assert_register_untouched(self.other_sso_register)

        response = self.api().delete(MANAGE_ENDPOINT, matching, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SSOPartnerIntegration.objects.filter(id=self.sso_register.id).exists())


class TestSSOAuthorizationFlow(TransactionTestCase):
    """The paths of `CustomAuthorizationView` that `test_sso.py` does not exercise."""

    def setUp(self):
        self.partner_client = create_partner_client()
        self.jwt_token = issue_token(self.partner_client)
        self.app = self.create_application(self.partner_client.name)
        self.user = UserFactory.create(username="userexample", password="correct_password")

    def create_application(self, name, redirect_uris=CALLBACK_URI):
        return Application.objects.create(
            name=name,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=redirect_uris,
        )

    def authorize(self, external_user_id, jwt_token=None, application=None, **extra):
        """Executes the SSO authorization request with the browser of the test."""
        params = {
            "client_id": (application or self.app).client_id,
            "external_user_id": external_user_id,
            "jwt_token": jwt_token or self.jwt_token,
            **extra,
        }

        return self.client.get(AUTHORIZE_ENDPOINT, params)

    def login(self, username="userexample"):
        self.assertTrue(self.client.login(username=username, password="correct_password"))

    def assert_callback(self, response, user, external_user_id):
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{CALLBACK_URI}/?nau_user={user.username}&external_user_id={external_user_id}")

    def test_existing_link_logs_in_its_owner_without_a_session(self):
        """
        A linked user arriving without a NAU session is logged in as the owner of the
        link, and no other register is created.
        """
        sso_register = SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")

        response = self.authorize("123456789")

        self.assert_callback(response, self.user, "123456789")
        self.assertEqual(response.wsgi_request.user, self.user)
        self.assertEqual(list(SSOPartnerIntegration.objects.all()), [sso_register])

    def test_existing_link_with_the_session_of_its_owner_creates_no_duplicate(self):
        sso_register = SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")
        self.login()

        for _ in range(2):
            response = self.authorize("123456789")
            self.assert_callback(response, self.user, "123456789")

        self.assertEqual(response.wsgi_request.user, self.user)
        self.assertEqual(list(SSOPartnerIntegration.objects.all()), [sso_register])

    def test_first_login_creates_the_link_with_the_expected_data(self):
        self.login()

        response = self.authorize("123456789")

        self.assert_callback(response, self.user, "123456789")
        sso_register = SSOPartnerIntegration.objects.get()
        self.assertEqual(sso_register.user, self.user)
        self.assertEqual(sso_register.partner_client, self.partner_client)
        self.assertEqual(sso_register.external_user_id, "123456789")

    def test_unlink_and_relink_to_another_account(self):
        """
        The support scenario of fccn/nau-technical#956: a link made with the wrong NAU
        account is removed through the management endpoint, and the person links again
        with the intended account.
        """
        intended_user = UserFactory.create(username="intended", password="correct_password")
        SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")

        # While the wrong link exists, the intended account is not able to claim the identification.
        self.login("intended")
        response = self.authorize("123456789")
        self.assertNotEqual(response.url.split("?")[0], f"{CALLBACK_URI}/")
        self.assertEqual(SSOPartnerIntegration.objects.get().user, self.user)

        partner_api = APIClient()
        partner_api.credentials(HTTP_AUTHORIZATION=f"Bearer {self.jwt_token}")
        response = partner_api.delete(MANAGE_ENDPOINT, {"external_user_id": "123456789"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SSOPartnerIntegration.objects.exists())

        self.login("intended")
        response = self.authorize("123456789")

        self.assert_callback(response, intended_user, "123456789")
        sso_register = SSOPartnerIntegration.objects.get()
        self.assertEqual(sso_register.user, intended_user)
        self.assertEqual(sso_register.partner_client, self.partner_client)

        # The account that was unlinked is free to be linked again, with another identification.
        self.login()
        response = self.authorize("987654321")
        self.assert_callback(response, self.user, "987654321")
        self.assertEqual(SSOPartnerIntegration.objects.count(), 2)

    def test_link_conflict_without_redirect_uri_goes_to_the_default_page(self):
        """
        An application without a redirect URI reports the link conflict on the default
        NAU page, carrying the same identifiable error.
        """
        application = self.create_application("without-redirect-uri", redirect_uris="")
        SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")
        self.login()

        response = self.authorize("987654321", application=application)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{DEFAULT_NAU_URI}/?error=sso_link_conflict")
        self.assertEqual(SSOPartnerIntegration.objects.get().external_user_id, "123456789")

    def test_restart_marker_is_harmless_when_the_session_belongs_to_the_owner(self):
        """A replayed restart URL does not abort a legitimate request."""
        SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")
        self.login()

        response = self.authorize("123456789", sso_session_restarted="1")

        self.assert_callback(response, self.user, "123456789")
        self.assertEqual(response.wsgi_request.user, self.user)

    def test_restart_marker_is_harmless_without_a_session(self):
        SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")

        response = self.authorize("123456789", sso_session_restarted="1")

        self.assert_callback(response, self.user, "123456789")
        self.assertEqual(response.wsgi_request.user, self.user)

    def test_restarted_flow_with_the_session_of_a_third_user_is_aborted(self):
        """
        When a session of someone else shows up again after the restart, the flow is
        aborted: nobody is authorized, the foreign session is dropped and the links
        stay as they were.
        """
        UserFactory.create(username="third", password="correct_password")
        sso_register = SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")
        self.login("third")

        response = self.authorize("123456789", sso_session_restarted="1")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, DEFAULT_NAU_URI)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(list(SSOPartnerIntegration.objects.all()), [sso_register])

    def test_restart_url_keeps_the_parameters_and_restarts_a_single_time(self):
        """
        The restart keeps every parameter of the original request, adds the marker once
        and, when followed, ends authorizing the owner of the link.
        """
        UserFactory.create(username="third", password="correct_password")
        SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")
        self.login("third")

        response = self.authorize("123456789")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(f"{AUTHORIZE_ENDPOINT}?"))
        self.assertEqual(response.url.count("sso_session_restarted=1"), 1)
        self.assertIn("external_user_id=123456789", response.url)
        self.assertIn(f"client_id={self.app.client_id}", response.url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

        response = self.client.get(response.url)

        self.assert_callback(response, self.user, "123456789")
        self.assertEqual(response.wsgi_request.user, self.user)

    def test_deactivated_partner_client_is_not_able_to_authorize(self):
        """A token of a partner client that was deactivated neither logs in nor links anybody."""
        SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")
        self.partner_client.is_active = False
        self.partner_client.save()

        response = self.authorize("123456789")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, DEFAULT_NAU_URI)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

        self.login()
        response = self.authorize("another-id")

        self.assertEqual(response.url, DEFAULT_NAU_URI)
        self.assertEqual(SSOPartnerIntegration.objects.count(), 1)

    def test_link_of_another_partner_client_does_not_log_in_its_owner(self):
        """
        The link is searched within the partner client of the token, so a partner is not
        able to open a session of a user that is only linked to a different partner.
        """
        other_partner_client = create_partner_client()
        other_jwt_token = issue_token(other_partner_client)
        other_application = self.create_application(other_partner_client.name)
        SSOPartnerIntegrationFactory.create(
            user=self.user, partner_client=self.partner_client, external_user_id="123456789")

        response = self.authorize("123456789", jwt_token=other_jwt_token, application=other_application)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/login?next="))
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(SSOPartnerIntegration.objects.count(), 1)

    def test_missing_or_malformed_parameters_never_fail(self):
        """A broken request ends on the default NAU page, never on an error page."""
        self.login()

        for params in [
            {},
            {"jwt_token": self.jwt_token},
            {"jwt_token": self.jwt_token, "client_id": "", "external_user_id": "123456789"},
            {"jwt_token": self.jwt_token, "client_id": "x" * 500, "external_user_id": "123456789"},
            {"jwt_token": "a.b.c", "client_id": self.app.client_id, "external_user_id": "123456789"},
            {"client_id": self.app.client_id, "external_user_id": "123456789"},
        ]:
            response = self.client.get(AUTHORIZE_ENDPOINT, params)

            self.assertEqual(response.status_code, 302, params)
            self.assertEqual(response.url, DEFAULT_NAU_URI, params)

        self.assertFalse(SSOPartnerIntegration.objects.exists())


class TestSSOUserSerializer(TestCase):
    """The representation of an SSO register sent to the partners."""

    def test_register_of_an_inactive_user_is_still_represented(self):
        """Deactivating the NAU account does not hide the link, the partner still needs to manage it."""
        user = UserFactory.create(username="inactive", email="inactive@example.com", is_active=False)
        sso_register = SSOPartnerIntegrationFactory.create(
            user=user, partner_client=create_partner_client(), external_user_id="123456789")

        self.assertEqual(
            SSOUserSerializer(sso_register).data,
            {"external_user_id": "123456789", "username": "inactive", "email": "inactive@example.com"},
        )

    def test_register_of_a_user_without_email_is_represented(self):
        user = UserFactory.create(username="noemail", email="")
        sso_register = SSOPartnerIntegrationFactory.create(
            user=user, partner_client=create_partner_client(), external_user_id="123456789")

        self.assertEqual(
            SSOUserSerializer(sso_register).data,
            {"external_user_id": "123456789", "username": "noemail", "email": ""},
        )

    def test_register_does_not_survive_its_user(self):
        """There is no register of a deleted user to be represented, it is removed with the user."""
        sso_register = SSOPartnerIntegrationFactory.create(
            partner_client=create_partner_client(), external_user_id="123456789")

        sso_register.user.delete()

        self.assertFalse(SSOPartnerIntegration.objects.filter(id=sso_register.id).exists())


class TestSSOConstraintsAreMigrated(TestCase):
    """
    The constraints of `SSOPartnerIntegration` were once declared in the model without a
    migration, so the database never enforced them. This keeps them in the migrations.

    The tests run without migrations, so they are enabled again only to read their files,
    nothing is applied to the database.
    """

    APP_LABEL = "nau_openedx_extensions"

    def load_migrations(self):
        """Returns the migrations loader, reading the migration files of every application."""
        with override_settings(MIGRATION_MODULES={}):
            return MigrationLoader(None, ignore_no_migrations=True)

    def test_sso_constraints_are_part_of_the_migrations(self):
        model_state = self.load_migrations().project_state().models[self.APP_LABEL, "ssopartnerintegration"]

        self.assertEqual(
            {constraint.name for constraint in model_state.options.get("constraints", [])},
            {
                "unique_sso_link_per_user_and_partner_client",
                "unique_sso_link_per_partner_client_and_external_user",
            },
        )
