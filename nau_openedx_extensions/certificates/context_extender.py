"""
Context extender module for edx-platform certificates
"""
from django.core.exceptions import ObjectDoesNotExist

from nau_openedx_extensions.edxapp_wrapper.registration import get_registration_extension_form
from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel


def update_cert_context(*args, **kwargs):
    """
    Updates certifcates context with custom data for the user
    """
    context = kwargs['context']
    user = kwargs['user']
    update_context_with_custom_form(user, NauUserExtendedModel, context)


def update_context_with_custom_form(user, custom_model, context):
    """
    Updates the context in-place with extra user information
    """
    custom_form = get_registration_extension_form()
    try:
        custom_model_instance = custom_model.objects.get(user=user)
    except ObjectDoesNotExist:
        # If a custom model does not exist for the user, just return
        return

    for field in custom_form.fields.keys():
        context.update({
            field: getattr(custom_model_instance, field, "")
        })
