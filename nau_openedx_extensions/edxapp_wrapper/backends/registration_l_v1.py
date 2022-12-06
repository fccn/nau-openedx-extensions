""" Registration edxapp backend abstraction """
from __future__ import absolute_import, unicode_literals

from common.djangoapps.third_party_auth.saml import EdXSAMLIdentityProvider  # pylint: disable=import-error


def get_edx_saml_identity_provider():
    """
    Gets edxapp SAML default identity provider class
    """
    return EdXSAMLIdentityProvider


def get_registration_extension_form(*args, **kwargs):
    """
    Convenience function for getting the custom form set in settings.REGISTRATION_EXTENSION_FORM.
    An example form app for this can be found at http://github.com/open-craft/custom-form-app
    """
    from openedx.core.djangoapps.user_authn.views.registration_form import \
        get_registration_extension_form  # pylint: disable=import-outside-toplevel, import-error, redefined-outer-name

    return get_registration_extension_form(*args, **kwargs)
