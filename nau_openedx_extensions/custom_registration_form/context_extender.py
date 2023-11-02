"""
Context extender module for edx-platform account page
"""
from __future__ import absolute_import, unicode_literals

import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import gettext as _

from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel
from nau_openedx_extensions.edxapp_wrapper import site_configuration_helpers as configuration_helpers

log = logging.getLogger(__name__)


def get_fields(custom_model_instance):
    """
    Get CC account visible fields from site configuration.
    """
    custom_fields = custom_model_instance._meta.fields
    allowed_fields = configuration_helpers.get_value(
        "NAU_ACCOUNTS_CC_VISIBLE_FIELDS", settings.NAU_ACCOUNTS_CC_VISIBLE_FIELDS
    )
    for field in custom_fields:
        if field.name not in allowed_fields:
            continue
        if isinstance(field, (models.CharField, models.TextField)):
            yield field


def update_account_view(context, user, **kwargs):
    """
    Updates the context from the student account view
    """
    extended_profile_fields = []
    custom_model_instance = None
    try:
        custom_model_instance = NauUserExtendedModel.objects.get(user=user)
    except ObjectDoesNotExist:
        # If a NauUserExtendedModel does not exist for the user, create an empty one
        custom_model_instance = NauUserExtendedModel()
    finally:
        for field in get_fields(custom_model_instance):
            extended_profile_fields.append(
                {
                    "field_name": _(field.name),  # pylint: disable=translation-of-non-string
                    "field_label": _(field.verbose_name),  # pylint: disable=translation-of-non-string
                    "field_type": "TextField" if not field.choices else "ListField",
                    "field_options": [] if not field.choices else field.choices,
                }
            )

    context["extended_profile_fields"].extend(extended_profile_fields)


def update_account_serializer(data, user, **kwargs):
    """
    Updates the data from the student account serializer
    """
    custom_model_instance = None
    try:
        custom_model_instance = NauUserExtendedModel.objects.get(user=user)
    except ObjectDoesNotExist:
        # If a NauUserExtendedModel does not exist for the user, create an empty one
        custom_model_instance = NauUserExtendedModel()
    finally:
        extended_profile = data.get("extended_profile", {})

        custom_profile = []
        for field in get_fields(custom_model_instance):
            custom_profile.append(
                {
                    "field_name": field.name,
                    "field_value": getattr(custom_model_instance, field.name, ""),
                }
            )
        extended_profile.extend(custom_profile)

        data["extended_profile"] = extended_profile


def partial_update(update, user, **kwargs):
    """
    Saves the data from the student account when something changes
    """
    if "extended_profile" in update:
        custom_model_instance = None
        try:
            custom_model_instance = NauUserExtendedModel.objects.get(user=user)
        except ObjectDoesNotExist:
            # If a NauUserExtendedModel does not exist for the user, create an empty one
            custom_model_instance = NauUserExtendedModel(user=user)
        finally:
            new_extended_profile = update["extended_profile"]

            for field in new_extended_profile:
                field_name = field["field_name"]
                new_value = field["field_value"]
                setattr(custom_model_instance, field_name, new_value)

            custom_model_instance.save()
