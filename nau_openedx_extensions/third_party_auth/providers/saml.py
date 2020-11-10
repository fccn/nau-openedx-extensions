"""
Slightly customized python-social-auth idp for SAML 2.0 support
"""
import logging
from importlib import import_module

from django.conf import settings

from nau_openedx_extensions.edxapp_wrapper.registration import EdXSAMLIdentityProvider, get_registration_extension_form

log = logging.getLogger(__name__)


class NauEdXSAMLIdentityProvider(EdXSAMLIdentityProvider):
    """
    Customized version of EdXSAMLIdentityProvider that can retrieve details beyond the standard
    details supported by the canonical upstream version.
    """

    def get_user_details(self, attributes):
        """
        Overrides `get_user_details` from the base class; retrieves those details,
        then updates the dict with values from whatever additional fields are desired.
        This method will be the final override for user details and it is called by
        the corresponding SAML backend. A valid 'field_mapping_rules' must be defined
        in order to fully support custom field defintions.
        """
        details = super(NauEdXSAMLIdentityProvider, self).get_user_details(attributes)
        field_mapping_rules = self.conf.get("field_mapping_rules", [])
        try:
            details.update(
                {
                    field["name"]: attributes[field["urn"]][0]
                    if field["urn"] in attributes
                    else None
                    for field in field_mapping_rules
                }
            )
        except KeyError as e:
            log.error(
                u"%s field missing to complete mappings based on provider configurations",
                str(e),
            )

        return details


def get_extended_saml_idp_choices(*args, **kwargs):  # pylint: disable=unused-argument
    """
    Returns a tuple with custom SAML idp choices. If an exception
    ocurs, it returns only the valid choices.
    """

    for idp in getattr(settings, "NAU_CUSTOM_SAML_IDENTITY_PROVIDERS", []):
        try:
            kwargs["choices"] += ((idp["provider_key"], idp["verbose_name"]),)
        except KeyError:
            log.error(u"%s could not be added as identity provider choice", idp)

    return kwargs["choices"]


def extend_saml_idp_classes(*args, **kwargs):  # pylint: disable=unused-argument
    """
    Return a dict containing SAML valid idps classes
    """

    for idp in getattr(settings, "NAU_CUSTOM_SAML_IDENTITY_PROVIDERS", []):
        try:
            module, klass = idp["provider_class"].rsplit(".", 1)
            idp_module = import_module(module)
            idp_class = getattr(idp_module, klass)
            kwargs["choices"][idp["provider_key"]] = idp_class
        except Exception:  # pylint: disable=broad-except
            log.error(
                u"%s could not be added as identity provider",
                kwargs["idp_identifier_string"],
            )

    return kwargs["choices"]


def _apply_saml_overrides(*args, **kwargs):  # pylint: disable=unused-argument
    """
    Applies custom saml override rules for custom
    registration forms
    """
    custom_form = get_registration_extension_form()
    form_desc = kwargs["form_desc"]

    for field_name, _field in custom_form.fields.items():
        visibility = kwargs["extra_settings"].get(field_name, "hidden")
        # applying commmon overrides
        form_desc.override_field_properties(
            field_name,
            required=False,
        )

        if visibility == "required":
            form_desc.override_field_properties(
                field_name,
                required=True,
            )
        if visibility == "hidden":
            form_desc.override_field_properties(
                field_name,
                field_type=visibility,
                label="",
                instructions="",
                restrictions={},
            )
