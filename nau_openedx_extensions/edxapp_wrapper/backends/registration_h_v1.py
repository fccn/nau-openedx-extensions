""" Registration edxapp backend abstraction """
from student import forms  # pylint: disable=import-error
from third_party_auth.saml import EdXSAMLIdentityProvider  # pylint: disable=import-error


def get_registration_extension_form():
    """
    Gets edxapp custom registration form
    """
    return forms.get_registration_extension_form()


def get_edx_saml_identity_provider():
    """
    Gets edxapp SAML default identity provider class
    """
    return EdXSAMLIdentityProvider
