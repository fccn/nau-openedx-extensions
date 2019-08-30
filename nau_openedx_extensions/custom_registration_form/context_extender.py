"""
Context extender module for edx-platform account page
"""
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext as _
from django.conf import settings
from django.db import models

from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

log = logging.getLogger(__name__)


def get_fields(custom_model_instance):
    custom_fields = custom_model_instance._meta.fields # pylint: disable=W0212
    allowed_fields = configuration_helpers.get_value('NAU_ACCOUNTS_CC_VISIBLE_FIELDS', settings.NAU_ACCOUNTS_CC_VISIBLE_FIELDS)
    for field in custom_fields:
        if field.name not in allowed_fields:
            continue
        if isinstance(field, models.TextField) or isinstance(field, models.CharField):
            yield field


def update_account_view(context, user, **kwargs):
    """
    Updates the context from the student account view
    """
    extended_profile_fields = []
    try:
        custom_model_instance = NauUserExtendedModel.objects.get(user=user)
    except ObjectDoesNotExist:
        # If a NauUserExtendedModel does not exist for the user, create an empty one
        custom_model_instance = NauUserExtendedModel()
    finally:
        for field in get_fields(custom_model_instance):
            extended_profile_fields.append({
                "field_name": _(field.name),
                "field_label": _(field.verbose_name),
                "field_type": 'TextField' if not field.choices else 'ListField',
                "field_options": [] if not field.choices else field.choices
            })

    context['extended_profile_fields'].extend(extended_profile_fields)


def update_account_serializer(data, user, **kwargs):
    """
    Updates the data from the student account serializer
    """
    try:
        custom_model_instance = NauUserExtendedModel.objects.get(user=user)
    except ObjectDoesNotExist:
        # If a NauUserExtendedModel does not exist for the user, create an empty one
        custom_model_instance = NauUserExtendedModel()
    finally:
        extended_profile = data.get('extended_profile', {})

        custom_profile = []
        for field in get_fields(custom_model_instance):
            custom_profile.append({
                "field_name": field.name,
                "field_value": getattr(custom_model_instance, field.name, "")
            })
        extended_profile.extend(custom_profile)

        data['extended_profile'] = extended_profile


def partial_update(update, user, **kwargs):
    """
    Saves the data from the student account when something changes
    """
    if 'extended_profile' in update:
        try:
            custom_model_instance = NauUserExtendedModel.objects.get(user=user)
        except ObjectDoesNotExist:
            # If a NauUserExtendedModel does not exist for the user, create an empty one
            custom_model_instance = NauUserExtendedModel(user=user)
        finally:
            new_extended_profile = update['extended_profile']

            for field in new_extended_profile:
                field_name = field['field_name']
                new_value = field['field_value']
                setattr(custom_model_instance, field_name, new_value)

            custom_model_instance.save()
