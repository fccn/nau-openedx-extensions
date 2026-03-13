"""Tests for SSO Partner Integration course enrollment filters."""

from unittest.mock import MagicMock, patch

from common.djangoapps.student.tests.factories import UserFactory
from django.test import TestCase, TransactionTestCase, override_settings
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory
from openedx_filters.learning.filters import CourseEnrollmentStarted
from rest_framework import status
from rest_framework.test import APIClient

from nau_openedx_extensions.custom_registration_form.factories import NauUserExtendedModelFactory
from nau_openedx_extensions.partner_integration.course_filters import FilterSSOPartnerAccountLink
from nau_openedx_extensions.partner_integration.factories import PartnerAPIClientFactory, SSOPartnerIntegrationFactory

MOCK_COURSE_SETTINGS_ENABLED = {"value": {"filter_enroll_only_if_sso_completed": True}}
MOCK_COURSE_SETTINGS_DISABLED = {"value": {}}


@patch(
    "nau_openedx_extensions.partner_integration.course_filters.get_other_course_settings",
    return_value=MOCK_COURSE_SETTINGS_ENABLED,
)
class FilterSSOPartnerAccountLinkTests(TestCase):
    """Test cases for FilterSSOPartnerAccountLink."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = UserFactory()
        self.course = CourseOverviewFactory()

    def test_filter_passes_when_user_has_valid_sso_record_and_course_allowed(self, _mock_settings):
        """Test filter passes when user has SSO record and course is in partner's scope."""
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org": self.course.org},
                "base_certificates_scope": {}
            }
        )
        SSOPartnerIntegrationFactory.create(user=self.user, partner_client=partner)

        filter_instance = FilterSSOPartnerAccountLink.run_filter(
            None, self.user, self.course.id, "honor"
        )
        self.assertEqual(filter_instance, {})

    def test_filter_raises_when_user_has_no_sso_record(self, _mock_settings):
        """Test filter raises PreventEnrollment when user has no SSO record."""
        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")

        error_message = str(context.exception)
        self.assertIn("ligação de conta", error_message)
        self.assertIn("parceiro", error_message)

    def test_filter_raises_when_partner_has_no_security_scope(self, _mock_settings):
        """Test filter raises PreventEnrollment when partner has empty security scope."""
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org": self.course.org},
                "base_certificates_scope": {}
            }
        )
        SSOPartnerIntegrationFactory.create(user=self.user, partner_client=partner)

        mock_sso = MagicMock()
        mock_sso.partner_client = MagicMock()
        mock_sso.partner_client.name = partner.name
        mock_sso.partner_client.query_security_scope = {"base_security_scope": {}, "base_certificates_scope": {}}

        with patch("nau_openedx_extensions.partner_integration.course_filters.apps.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.objects.get.return_value = mock_sso
            mock_get_model.return_value = mock_model

            with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
                FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")

            error_message = str(context.exception)
            self.assertIn("acesso configurado", error_message)

    def test_filter_raises_when_course_not_in_partner_scope(self, _mock_settings):
        """Test filter raises PreventEnrollment when course is not allowed by partner."""
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org": "different_org"},
                "base_certificates_scope": {}
            }
        )
        SSOPartnerIntegrationFactory.create(user=self.user, partner_client=partner)

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as context:
            FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")

        error_message = str(context.exception)
        self.assertIn("permissão", error_message)
        self.assertIn("curso", error_message)

    def test_filter_passes_with_multiple_orgs_in_scope(self, _mock_settings):
        """Test filter passes when course org is one of multiple allowed orgs."""
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org__in": ["org1", self.course.org, "org3"]},
                "base_certificates_scope": {}
            }
        )
        SSOPartnerIntegrationFactory.create(user=self.user, partner_client=partner)

        result = FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")
        self.assertEqual(result, {})

    def test_filter_passes_with_course_id_in_scope(self, _mock_settings):
        """Test filter passes when specific course IDs are allowed."""
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {
                    "org": self.course.org,
                    "id__in": [str(self.course.id)]
                },
                "base_certificates_scope": {}
            }
        )
        SSOPartnerIntegrationFactory.create(user=self.user, partner_client=partner)

        result = FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")
        self.assertEqual(result, {})

    def test_is_course_allowed_for_partner_with_valid_scope(self, _mock_settings):
        """Test _is_course_allowed_for_partner with valid scope."""
        base_security_scope = {"org": self.course.org}
        result = FilterSSOPartnerAccountLink._is_course_allowed_for_partner(
            self.course.id, base_security_scope
        )
        self.assertTrue(result)

    def test_is_course_allowed_for_partner_with_invalid_scope(self, _mock_settings):
        """Test _is_course_allowed_for_partner with invalid scope."""
        base_security_scope = {"org": "non_existent_org"}
        result = FilterSSOPartnerAccountLink._is_course_allowed_for_partner(
            self.course.id, base_security_scope
        )
        self.assertFalse(result)

    def test_is_course_allowed_for_partner_handles_exceptions(self, _mock_settings):
        """Test _is_course_allowed_for_partner handles exceptions gracefully."""
        with patch("django.apps.apps.get_model") as mock_get_model:
            mock_model = MagicMock()
            mock_model.objects.filter.side_effect = Exception("Database error")
            mock_get_model.return_value = mock_model

            base_security_scope = {"org": self.course.org}
            result = FilterSSOPartnerAccountLink._is_course_allowed_for_partner(
                self.course.id, base_security_scope
            )
            self.assertFalse(result)

    def test_filter_logs_when_user_has_no_sso_record(self, _mock_settings):
        """Test filter logs warning when user has no SSO record."""
        with patch("nau_openedx_extensions.partner_integration.course_filters.logger") as mock_logger:
            with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
                FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")

            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args[0][0]
            self.assertIn("no SSO partner integration record", call_args)

    def test_filter_logs_when_course_not_allowed(self, _mock_settings):
        """Test filter logs warning when course is not allowed by partner."""
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org": "different_org"},
                "base_certificates_scope": {}
            }
        )
        SSOPartnerIntegrationFactory.create(user=self.user, partner_client=partner)

        with patch("nau_openedx_extensions.partner_integration.course_filters.logger") as mock_logger:
            with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
                FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")

            mock_logger.warning.assert_called()
            call_args = mock_logger.warning.call_args[0][0]
            self.assertIn("does not have access to course", call_args)

    def test_filter_logs_success(self, _mock_settings):
        """Test filter logs info when validation passes."""
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org": self.course.org},
                "base_certificates_scope": {}
            }
        )
        SSOPartnerIntegrationFactory.create(user=self.user, partner_client=partner)

        with patch("nau_openedx_extensions.partner_integration.course_filters.logger") as mock_logger:
            FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")

            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            self.assertIn("validated for enrollment", call_args)

    def test_filter_skipped_when_course_setting_not_enabled(self, mock_settings):
        """Test filter is a no-op when filter_enroll_only_if_sso_completed is not set."""
        mock_settings.return_value = MOCK_COURSE_SETTINGS_DISABLED
        result = FilterSSOPartnerAccountLink.run_filter(None, self.user, self.course.id, "honor")
        self.assertEqual(result, {})


FILTER_PIPELINE_CONFIG = {
    "org.openedx.learning.course.enrollment.started.v1": {
        "fail_silently": False,
        "pipeline": [
            "nau_openedx_extensions.partner_integration.course_filters.FilterSSOPartnerAccountLink"
        ]
    }
}


@patch(
    "nau_openedx_extensions.partner_integration.course_filters.get_other_course_settings",
    return_value=MOCK_COURSE_SETTINGS_ENABLED,
)
class FilterSSOPartnerAccountLinkIntegrationTests(TransactionTestCase):
    """
    Integration tests for FilterSSOPartnerAccountLink.

    These tests validate the filter works end-to-end when triggered via
    the enroll-user API endpoint, with the filter pipeline enabled via
    OPEN_EDX_FILTERS_CONFIG and the course setting filter_enroll_only_if_sso_completed.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.http_client = APIClient()
        self.endpoint = "/nau-openedx-extensions/partner-integration/enroll-user/"
        self.auth_endpoint = "/nau-openedx-extensions/partner-integration/auth-token/"

        # Create a partner client with a known password and valid security scope
        self.course = CourseOverviewFactory()
        self.partner_client = PartnerAPIClientFactory.create(
            is_active=True,
            query_security_scope={
                "base_security_scope": {"org": self.course.org},
                "base_certificates_scope": {}
            }
        )
        self.partner_client.password = "integration_test_password"
        self.partner_client.save()

    def _authenticate(self):
        """Authenticate partner client and return access token."""
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token integration_test_password",
            HTTP_X_CLIENT_ID=self.partner_client.client_id,
        )
        response = self.http_client.post(self.auth_endpoint, format="json")
        assert response.status_code == 200, f"Auth failed: {response.data}"
        return response.data["access_token"]

    def _enroll_via_api(self, access_token, course_id, email):
        """Call the enroll-user API endpoint."""
        self.http_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        return self.http_client.post(
            self.endpoint,
            data={"course": str(course_id), "email": email},
            format="json",
        )

    @override_settings(OPEN_EDX_FILTERS_CONFIG=FILTER_PIPELINE_CONFIG)
    def test_api_enrollment_blocked_when_user_has_no_sso_record(self, _mock_settings):
        """
        Integration test: enrollment via API is blocked when the user has no
        SSOPartnerIntegration record.

        The filter raises PreventEnrollment, which propagates through
        enrollment_api.add_enrollment() and is caught by the facade,
        resulting in a 403 Forbidden response with the filter's error message.
        """
        access_token = self._authenticate()

        external_user = NauUserExtendedModelFactory.create()
        external_user.user.email = "no_sso_record@example.com"
        external_user.user.save()

        response = self._enroll_via_api(
            access_token, self.course.id, external_user.user.email
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(
            "A ligação de conta com a plataforma do parceiro não foi concluída",
            response.data["error"]
        )

    @override_settings(OPEN_EDX_FILTERS_CONFIG=FILTER_PIPELINE_CONFIG)
    def test_api_enrollment_blocked_when_partner_has_empty_security_scope(self, _mock_settings):
        """
        Integration test: enrollment via API is blocked when the partner
        has an empty base_security_scope.

        A separate partner with empty scope is used to create the SSO record,
        but this test calls the enroll endpoint authenticated as the main
        partner. The filter checks the SSO record's partner, not the
        authenticated partner.
        """
        access_token = self._authenticate()

        # Create a different partner with empty security scope
        empty_scope_partner = PartnerAPIClientFactory.create(
            is_active=True,
            query_security_scope={
                "base_security_scope": {"org": self.course.org},
                "base_certificates_scope": {}
            }
        )
        # Manually clear the scope after creation (bypassing validation)
        from nau_openedx_extensions.partner_integration.models import PartnerAPIClient
        PartnerAPIClient.objects.filter(pk=empty_scope_partner.pk).update(
            query_security_scope={"base_security_scope": {}, "base_certificates_scope": {}}
        )
        empty_scope_partner.refresh_from_db()

        external_user = NauUserExtendedModelFactory.create()
        external_user.user.email = "empty_scope@example.com"
        external_user.user.save()

        SSOPartnerIntegrationFactory.create(
            user=external_user.user,
            partner_client=empty_scope_partner
        )

        response = self._enroll_via_api(
            access_token, self.course.id, external_user.user.email
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(
            "O parceiro de integração não tem acesso configurado para nenhum curso",
            response.data["error"]
        )

    @override_settings(OPEN_EDX_FILTERS_CONFIG=FILTER_PIPELINE_CONFIG)
    def test_api_enrollment_blocked_when_course_not_in_partner_scope(self, _mock_settings):
        """
        Integration test: enrollment via API is blocked when the course
        is not within the SSO partner's base_security_scope.
        """
        access_token = self._authenticate()

        # Create a partner with a different org scope
        different_org_partner = PartnerAPIClientFactory.create(
            is_active=True,
            query_security_scope={
                "base_security_scope": {"org": "completely_different_org"},
                "base_certificates_scope": {}
            }
        )

        external_user = NauUserExtendedModelFactory.create()
        external_user.user.email = "wrong_scope@example.com"
        external_user.user.save()

        SSOPartnerIntegrationFactory.create(
            user=external_user.user,
            partner_client=different_org_partner
        )

        response = self._enroll_via_api(
            access_token, self.course.id, external_user.user.email
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn(
            "O parceiro de integração não tem permissão para inscrever utilizadores neste curso",
            response.data["error"]
        )

    @override_settings(OPEN_EDX_FILTERS_CONFIG=FILTER_PIPELINE_CONFIG)
    def test_api_enrollment_succeeds_when_all_conditions_met(self, _mock_settings):
        """
        Integration test: enrollment via API succeeds when the user has a
        valid SSO record and the partner's scope includes the course.
        """
        access_token = self._authenticate()

        external_user = NauUserExtendedModelFactory.create()
        external_user.user.email = "valid_sso@example.com"
        external_user.user.save()

        SSOPartnerIntegrationFactory.create(
            user=external_user.user,
            partner_client=self.partner_client
        )

        response = self._enroll_via_api(
            access_token, self.course.id, external_user.user.email
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["course_id"], str(self.course.id))
        self.assertEqual(response.data["user_email"], "valid_sso@example.com")

    @override_settings(OPEN_EDX_FILTERS_CONFIG=FILTER_PIPELINE_CONFIG)
    def test_api_enrollment_succeeds_with_multiple_orgs_in_scope(self, _mock_settings):
        """
        Integration test: enrollment via API succeeds when the partner has
        org__in scope containing the course's org among multiple orgs.
        """
        multi_org_partner = PartnerAPIClientFactory.create(
            is_active=True,
            query_security_scope={
                "base_security_scope": {
                    "org__in": ["org_alpha", self.course.org, "org_gamma"]
                },
                "base_certificates_scope": {}
            }
        )
        multi_org_partner.password = "integration_test_password"
        multi_org_partner.save()

        # Authenticate as the multi-org partner
        self.http_client.credentials(
            HTTP_AUTHORIZATION="Token integration_test_password",
            HTTP_X_CLIENT_ID=multi_org_partner.client_id,
        )
        response = self.http_client.post(self.auth_endpoint, format="json")
        assert response.status_code == 200
        access_token = response.data["access_token"]

        external_user = NauUserExtendedModelFactory.create()
        external_user.user.email = "multi_org@example.com"
        external_user.user.save()

        SSOPartnerIntegrationFactory.create(
            user=external_user.user,
            partner_client=multi_org_partner
        )

        response = self._enroll_via_api(
            access_token, self.course.id, external_user.user.email
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["course_id"], str(self.course.id))

    def test_api_enrollment_succeeds_without_filter_configured(self, _mock_settings):
        """
        Baseline test: enrollment via API succeeds normally when the
        OPEN_EDX_FILTERS_CONFIG is not set (filter pipeline is not active).

        This ensures the filter doesn't interfere when not configured.
        """
        access_token = self._authenticate()

        external_user = NauUserExtendedModelFactory.create()
        external_user.user.email = "no_filter@example.com"
        external_user.user.save()

        response = self._enroll_via_api(
            access_token, self.course.id, external_user.user.email
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["course_id"], str(self.course.id))

    @override_settings(OPEN_EDX_FILTERS_CONFIG=FILTER_PIPELINE_CONFIG)
    def test_api_enrollment_succeeds_when_course_setting_not_enabled(self, mock_settings):
        """
        Integration test: enrollment succeeds even with filter pipeline active,
        when the course does NOT have filter_enroll_only_if_sso_completed set.

        This verifies that the filter is a no-op for courses without the setting.
        """
        mock_settings.return_value = MOCK_COURSE_SETTINGS_DISABLED
        access_token = self._authenticate()

        external_user = NauUserExtendedModelFactory.create()
        external_user.user.email = "no_course_setting@example.com"
        external_user.user.save()

        # User has no SSO record, but filter should not block because course setting is off
        response = self._enroll_via_api(
            access_token, self.course.id, external_user.user.email
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["course_id"], str(self.course.id))
