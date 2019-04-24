"""
Slightly customized python-social-auth idp for SAML 2.0 support
"""
import logging
from third_party_auth.saml import EdXSAMLIdentityProvider

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
        details = super(EdXSAMLIdentityProvider, self).get_user_details(attributes)
        field_mapping_rules = self.conf.get('field_mapping_rules', [])
        try:
            details.update({
                field['name']: attributes[field['urn']][0] if field['urn'] in attributes else None
                for field in field_mapping_rules
            })
        except KeyError as e:
            log.error(
                '%s field missing to complete mappings based on provider configurations',
                str(e)
            )

        return details
