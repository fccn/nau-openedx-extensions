"""
Context extender module for edx-platform certificates
"""
from __future__ import absolute_import, unicode_literals

import logging

import six
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.translation import ugettext as _

from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel
from nau_openedx_extensions.edxapp_wrapper.grades import get_course_grades

log = logging.getLogger(__name__)


def update_cert_context(context, user, course, **kwargs):
    """
    Updates certifcates context with custom data for the user within
    the course context
    """
    nau_cert_settings = course.cert_html_view_overrides.get("nau_certs_settings")

    update_context_with_custom_form(user, NauUserExtendedModel, context)
    if nau_cert_settings:
        update_context_with_grades(
            user, course, context, nau_cert_settings, kwargs["user_certificate"]
        )
        update_context_with_interpolated_strings(
            context, nau_cert_settings, kwargs["certificate_language"]
        )


def update_context_with_custom_form(user, custom_model, context):
    """
    Updates the context in-place with extra user information
    """
    try:
        custom_model_instance = custom_model.objects.get(user=user)
    except ObjectDoesNotExist:
        # If a custom model does not exist for the user, create an empty one
        custom_model_instance = custom_model()
    finally:
        for field in custom_model_instance._meta.fields:

            if isinstance(field, (models.BooleanField, models.CharField, models.TextField)):
                context_element = {
                    field.name: getattr(custom_model_instance, field.name, "")
                }
                context.update(context_element)


def update_context_with_grades(user, course, context, settings, user_certificate):
    """
    Updates certifcates context with grades data for the user
    """
    # always add `user certificate` grade context
    context.update(
        {
            "certificate_final_grade": user_certificate.grade,
        }
    )

    if settings.get("calculate_grades_context", False):
        try:
            grades = get_course_grades(user, course)
            context_element = {
                "course_letter_grade": grades.letter_grade or "",
                "user_has_approved_course": grades.passed,
                "course_percent_grade": grades.percent,
            }
        except Exception:  # pylint: disable=broad-except
            log.error(
                "Could not get grades for user %s in %s",
                user.username,
                course.display_name,
            )
        else:
            context.update(context_element)


def update_context_with_interpolated_strings(context, settings, certificate_language):
    """
    Updates certificate context using custom interpolated strings.
    Applies the corresponding translation before updating the context.
    """
    interpolated_strings = get_interpolated_strings(settings, certificate_language)

    if interpolated_strings:
        for key, value in six.iteritems(interpolated_strings):
            try:
                # Also try to translate the string if defined in platform .po
                formatted_string = _(value).format(**context)  # pylint: disable=translation-of-non-string
            except (ValueError, AttributeError, KeyError):
                log.error(
                    "Failed to add value (%s) as formatted string in the certificate context",
                    value,
                )
                continue
            else:
                context.update({key: formatted_string})


def get_interpolated_strings(settings, certificate_language):
    """
    Returns a dict with custom interpolated strings available for a certificate language.
    Returns an empty dict if it cant find a string for the given language.
    """
    lang_interpolated_strings = {}
    multilang_interpolated_strings = settings.get("interpolated_strings")
    if multilang_interpolated_strings:
        for key, value in six.iteritems(multilang_interpolated_strings):
            try:
                for lang, string in six.iteritems(value):
                    if lang in certificate_language:
                        lang_interpolated_strings[key] = string
                        break
            except AttributeError:
                log.error(
                    "Failed to read (%s) as formatted string in the certificate context",
                    key,
                )
                continue

    return lang_interpolated_strings
