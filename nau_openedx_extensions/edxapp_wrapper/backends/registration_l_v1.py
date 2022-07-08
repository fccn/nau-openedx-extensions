""" Registration edxapp backend abstraction """
from __future__ import absolute_import, unicode_literals

from openedx.core.djangoapps.user_authn.views.registration_form import get_registration_extension_form

from common.djangoapps.third_party_auth.saml import EdXSAMLIdentityProvider  # pylint: disable=import-error


def get_edx_saml_identity_provider():
    """
    Gets edxapp SAML default identity provider class
    """
    return EdXSAMLIdentityProvider
