"""
Tests for the account settings context extender.
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from nau_openedx_extensions.custom_registration_form.context_extender import (
    get_fields,
    partial_update,
    update_account_serializer,
)
from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel

VISIBLE_FIELDS = ["employment_situation", "nif", "allow_newsletter", "nuts", "cae4"]


@override_settings(NAU_ACCOUNTS_CC_VISIBLE_FIELDS=VISIBLE_FIELDS)
class AccountContextExtenderTest(SimpleTestCase):
    """
    The account page reaches NauUserExtendedModel only through these hooks, so what they
    expose and what they let through is the whole access control for those fields.
    """

    def setUp(self):
        super().setUp()
        self.user = MagicMock(username="kellogs")
        self.instance = NauUserExtendedModel(
            nif="123456789",
            cc_nif="987654321",
            nuts="norte_cavado",
            data_authorization=True,
        )
        self.instance.save = MagicMock()
        self.instance.full_clean = MagicMock()

    def partial_update(self, extended_profile):
        """Run partial_update against the in-memory instance, without touching the database."""
        with patch.object(NauUserExtendedModel.objects, "get", return_value=self.instance):
            partial_update({"extended_profile": extended_profile}, self.user)

    def test_only_allowlisted_fields_are_exposed(self):
        """A field missing from NAU_ACCOUNTS_CC_VISIBLE_FIELDS never reaches the page."""
        assert {field.name for field in get_fields(self.instance)} == set(VISIBLE_FIELDS)

    def test_editing_one_field_leaves_the_others_alone(self):
        """
        This is the property the PROFILE_EXTENSION_FORM path does not have: there the form
        is bound with the submitted data, so anything not sent is saved as empty.
        """
        self.partial_update([{"field_name": "nuts", "field_value": "norte_ave"}])

        assert self.instance.nuts == "norte_ave"
        assert self.instance.nif == "123456789"
        assert self.instance.cc_nif == "987654321"
        assert self.instance.data_authorization is True
        self.instance.save.assert_called_once()

    def test_a_field_in_both_sources_is_returned_once_from_the_model(self):
        """
        The serializer fills extended_profile from UserProfile.meta before this hook
        runs. Appending on top left two entries with the same field_name, and the
        account page takes the first, so it showed the stale meta value while the
        course gate read the model. See fccn/nau-technical#1050.
        """
        data = {"extended_profile": [
            {"field_name": "nif", "field_value": "000000000"},
            {"field_name": "bio", "field_value": "from meta"},
        ]}

        with patch.object(NauUserExtendedModel.objects, "get", return_value=self.instance):
            update_account_serializer(data, self.user)

        entries = data["extended_profile"]
        assert [e["field_name"] for e in entries].count("nif") == 1
        assert next(e["field_value"] for e in entries if e["field_name"] == "nif") == "123456789"
        # A meta-only field the model knows nothing about is left alone.
        assert next(e["field_value"] for e in entries if e["field_name"] == "bio") == "from meta"

    def test_fields_outside_the_allowlist_are_refused(self):
        """A crafted request must not be able to withdraw consent or rewrite citizen card data."""
        self.partial_update([
            {"field_name": "data_authorization", "field_value": False},
            {"field_name": "cc_nif", "field_value": "000000000"},
        ])

        assert self.instance.data_authorization is True
        assert self.instance.cc_nif == "987654321"
        self.instance.save.assert_not_called()
