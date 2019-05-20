""" Registration backend abstraction """
from importlib import import_module
from django.conf import settings


def get_registration_extension_form(*args, **kwargs):
    """ Gets the registration extension form """

    backend_module = settings.NAU_REGISTRATION_MODULE
    backend = import_module(backend_module)

    return backend.get_registration_extension_form(*args, **kwargs)


def get_edx_saml_identity_provider(*args, **kwargs):
    """ Gets the registration extension form """

    backend_module = settings.NAU_REGISTRATION_MODULE
    backend = import_module(backend_module)

    return backend.get_edx_saml_identity_provider(*args, **kwargs)


EdXSAMLIdentityProvider = get_edx_saml_identity_provider()
