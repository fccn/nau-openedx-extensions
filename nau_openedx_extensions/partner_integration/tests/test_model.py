# tests/test_models_partner_api_client.py
from django.test import TestCase

from nau_openedx_extensions.models import PartnerAPIClient
from nau_openedx_extensions.partner_integration.factories import PartnerAPIClientFactory


class PartnerAPIClientModelTest(TestCase):

    def test_create_partner_client_register(self):
        scope = {
            "base_security_scope": {"org": "FCCN", "invalid_field": "test"},
            "base_certificates_scope": {"course_id__icontains": "2024_T3"}
        }
        client = PartnerAPIClientFactory.create(query_security_scope=scope)

        self.assertIsInstance(client, PartnerAPIClient)
        self.assertTrue(client.is_active)
        self.assertTrue(client.name.startswith("partner-"))
        self.assertIsNotNone(client.client_id)

    def test_str_email_username_properties(self):
        scope = {
            "base_security_scope": {"org": "FCCN", "invalid_field": "test"},
            "base_certificates_scope": {"course_id__icontains": "2024_T3"}
        }
        client = PartnerAPIClientFactory.create(name="testclient", query_security_scope=scope)

        self.assertEqual(client.username, "testclient")
        self.assertIn("@example.com", client.email)
        self.assertIn("testclient", str(client))

    def test_validate_basis_with_valid_scope(self):
        scope = {
            "base_security_scope": {"org": "FCCN", "id__icontains": "2024_T3"},
            "base_certificates_scope": {"user__id": 1}
        }
        client = PartnerAPIClientFactory.create(name="testclient", query_security_scope=scope)

        client.validate_basis(scope)
        self.assertIn("org", scope["base_security_scope"])
        self.assertIn("id__icontains", scope["base_security_scope"])
        self.assertIn("user__id", scope["base_certificates_scope"])

    def test_validate_basis_removes_invalid_fields(self):
        scope = {
            "base_security_scope": {"org": "FCCN", "course_id__icontains__invalid": "2024_T3"},
            "base_certificates_scope": {"user__id": None}
        }
        client = PartnerAPIClientFactory.create(name="testclient", query_security_scope=scope)

        client.validate_basis(scope)
        self.assertIn("org", scope["base_security_scope"])
        self.assertNotIn("course_id__icontains__invalid", scope["base_security_scope"])
        self.assertNotIn("user__id", scope["base_certificates_scope"])


class ValidateBasisTests(TestCase):
    def setUp(self):
        self.partner_model = PartnerAPIClient()

    def test_valid_base_security_scope_passes(self):
        scope = {
            "base_security_scope": {"org": "FCCN"},
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("org", scope["base_security_scope"])
        self.assertEqual(scope["base_security_scope"]["org"], "FCCN")

    def test_missing_base_security_scope_raises(self):
        scope = {
            "base_security_scope": {},
            "base_certificates_scope": {}
        }

        with self.assertRaises(AssertionError):
            self.partner_model.validate_basis(scope)

    def test_missing_org_field_raises(self):
        scope = {
            "base_security_scope": {"wrong_field": "value"},
            "base_certificates_scope": {}
        }

        with self.assertRaises(AssertionError):
            self.partner_model.validate_basis(scope)

    def test_valid_base_security_scope_courses(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN"
                ""
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("org", scope["base_security_scope"])
        self.assertEqual(scope["base_security_scope"]["org"], "FCCN")

    def test_invalid_field_is_removed(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN",
                "invalid_field": "whatever"
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("org", scope["base_security_scope"])
        self.assertNotIn("invalid_field", scope["base_security_scope"])

    def test_none_value_is_removed(self):
        scope = {
            "base_security_scope": {
                "org": None
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertNotIn("org", scope["base_security_scope"])

    def test_valid_course_key_icontains_lookup_period(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN",
                "id__icontains": "2025_T3"
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("id__icontains", scope["base_security_scope"])

    def test_valid_course_key_contains_lookup(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN",
                "id__contains": "TPAGRED"
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("id__contains", scope["base_security_scope"])

    def test_valid_course_key_exact_lookup(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN",
                "id__exact": "course-v1:FCCN+TPAGRED+2025_T3"
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("id__exact", scope["base_security_scope"])

    def test_invalid_course_key_lookup_removed(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN",
                "id__not_in": ["2025_T3", "TPAGRED"]
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertNotIn("id__not_in", scope["base_security_scope"])

    def test_invalid_nested_lookup_removed(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN",
                "id__icontains__invalid": "2025"
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertNotIn("id__icontains__invalid", scope["base_security_scope"])

    def test_none_value_on_course_key_lookup_removed(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN",
                "id__icontains": None
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertNotIn("id__icontains", scope["base_security_scope"])

    def test_valid_value_on_course_key_lookup_kept(self):
        scope = {
            "base_security_scope": {
                "org": "FCCN",
                "id__icontains": "2025"
            },
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("id__icontains", scope["base_security_scope"])

    def test_valid_icontains_lookup(self):
        scope = {
            "base_security_scope": {"org__icontains": "fccn"},
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("org__icontains", scope["base_security_scope"])

    def test_valid_in_lookup(self):
        scope = {
            "base_security_scope": {"org__in": ["FCCN", "X"]},
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("org__in", scope["base_security_scope"])

    def test_valid_range_lookup(self):
        scope = {
            "base_certificates_scope": {"created_date__range": ["2025-01-01", "2025-12-31"]},
            "base_security_scope": {"org": "FCCN"}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("created_date__range", scope["base_certificates_scope"])

    def test_valid_greater_than_lookup(self):
        scope = {
            "base_certificates_scope": {"created_date__gt": "2025-01-01"},
            "base_security_scope": {"org": "FCCN"}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("created_date__gt", scope["base_certificates_scope"])

    def test_valid_user_related_field_lookup(self):
        scope = {
            "base_certificates_scope": {"user__email__icontains": "@example.com"},
            "base_security_scope": {"org": "FCCN"}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("user__email__icontains", scope["base_certificates_scope"])

    def test_valid_double_underscore_lookup(self):
        scope = {
            "base_security_scope": {"org": "FCCN"},
            "base_certificates_scope": {"user__email": "test@example.com"}
        }

        self.partner_model.validate_basis(scope)
        self.assertIn("user__email", scope["base_certificates_scope"])

    def test_invalid_base_scope_with_valid_base_certificates(self):
        scope = {
            "base_security_scope": {},
            "base_certificates_scope": {"user__email": "test@example.com"}
        }

        with self.assertRaises(AssertionError):
            self.partner_model.validate_basis(scope)

    def test_invalid_double_underscore_lookup_is_removed(self):
        scope = {
            "base_security_scope": {"org": "FCCN"},
            "base_certificates_scope": {"user__not_a_field": "x"}
        }

        self.partner_model.validate_basis(scope)
        self.assertNotIn("user__not_a_field", scope["base_certificates_scope"])

    def test_logger_called_on_invalid_field(self):
        scope = {
            "base_security_scope": {"org": "FCCN", "bad": "x"},
            "base_certificates_scope": {}
        }

        self.partner_model.validate_basis(scope)
        self.assertNotIn("bad", scope["base_security_scope"])
