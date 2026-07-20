from common.djangoapps.student.tests.factories import UserFactory
from django.contrib.admin.sites import AdminSite
from django.db.utils import IntegrityError
from django.test import TestCase

from nau_openedx_extensions.partner_integration.admin import SSOPartnerIntegrationAdmin
from nau_openedx_extensions.partner_integration.factories import PartnerAPIClientFactory, SSOPartnerIntegrationFactory
from nau_openedx_extensions.partner_integration.models import SSOPartnerIntegration


class SSOPartnerIntegrationAdminTests(TestCase):
    """Unit tests for the SSOPartnerIntegrationAdmin class."""
    def setUp(self):
        self.site = AdminSite()
        self.admin = SSOPartnerIntegrationAdmin(SSOPartnerIntegration, self.site)

    def test_admin_search_and_list_display_are_configured(self):
        """
        Test that the search_fields and list_display attributes
        of the admin class are correctly configured.
        """
        self.assertEqual(
            self.admin.search_fields,
            (
                'user__username',
                'user__email',
                'user__id',
                'external_user_id',
                'partner_client__name',
            )
        )
        self.assertEqual(
            self.admin.list_display,
            (
                'user',
                'openedx_email',
                'partner_client',
                'external_user_id',
                'created_at',
                'updated_at',
            )
        )

    def test_openedx_email_returns_user_email(self):
        """
        Test that the openedx_email method returns the correct user email.
        """
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org": "ORG"},
                "base_certificates_scope": {}
            }
        )
        user = UserFactory.create(username='testuser')
        sso_record = SSOPartnerIntegrationFactory.create(
            user=user, partner_client=partner)

        self.assertEqual(self.admin.openedx_email(sso_record), user.email)

    def test_external_user_id_is_required(self):
        """
        Test that the required fields for SSOPartnerIntegration are enforced.
        """
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org": "ORG"},
                "base_certificates_scope": {}
            }
        )
        user = UserFactory.create(username='testuser')

        with self.assertRaises(IntegrityError):
            SSOPartnerIntegrationFactory.create(
                user=user, partner_client=partner, external_user_id=None
            )

    def test_partner_client_is_required(self):
        """
        Test that the required fields for SSOPartnerIntegration are enforced.
        """
        user = UserFactory.create(username='testuser')

        with self.assertRaises(IntegrityError):
            SSOPartnerIntegrationFactory.create(
                user=user, partner_client=None, external_user_id="external-user-1"
            )

    def test_user_is_required(self):
        """
        Test that the required fields for SSOPartnerIntegration are enforced.
        """
        partner = PartnerAPIClientFactory.create(
            query_security_scope={
                "base_security_scope": {"org": "ORG"},
                "base_certificates_scope": {}
            }
        )

        with self.assertRaises(IntegrityError):
            SSOPartnerIntegrationFactory.create(
                user=None, partner_client=partner, external_user_id="external-user-1"
            )

    def test_readonly_fields_are_configured(self):
        """
        Test that the readonly_fields attribute of the admin class is correctly configured.
        """
        self.assertEqual(
            self.admin.readonly_fields,
            ('created_at', 'updated_at')
        )
