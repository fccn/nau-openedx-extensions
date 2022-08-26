"""
Context extender module for edx-platform certificates
"""
from __future__ import absolute_import, unicode_literals

import logging

import six
from django.conf import settings
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
            user, course, context, nau_cert_settings, kwargs["user_certificate"], kwargs["certificate_language"]
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


def update_context_with_grades(user, course, context, nau_certs_settings, user_certificate, certificate_language):
    """
    Updates certifcates context with grades data for the user
    """
    # always add `user certificate` grade context
    context.update(
        {
            "certificate_final_grade": user_certificate.grade,
        }
    )

    if nau_certs_settings.get("calculate_grades_context", False):
        try:
            grades = get_course_grades(user, course)
            # The `grades.percent` is a number from 0 to 1.
            grade_percent = grades.percent
            # grade_percent = 0.64001
            context_element = {
                "course_letter_grade": grades.letter_grade or "",
                "user_has_approved_course": grades.passed,
                "course_percent_grade": grade_percent,
                "course_grade_scale_10": grade_percent * 10,
                "course_grade_scale_20": grade_percent * 20,
            }
        except Exception:  # pylint: disable=broad-except
            log.error(
                "Could not get grades for user %s in %s",
                user.username,
                course.display_name,
            )
        else:
            context.update(context_element)

        course_qualitative_grade_config = nau_certs_settings.get("course_qualitative_grade")
        if course_qualitative_grade_config:
            course_qualitative_grade(user, course, context, course_qualitative_grade_config, certificate_language)

def course_qualitative_grade(user, course, context, course_qualitative_grade_config, certificate_language):
    """
    Custom per course qualitative grade generator.

    "nau_certs_settings": {
        "interpolated_strings": {
            "accomplishment_copy_course_description": {
                "pt": ", com nota de numérica de {course_percent_grade:.0%} numa escala de 0 a 10 e nota qualitativa de {course_grade_qualitative}.",
                "en": ", with a numberic grade of {course_percent_grade:.0%} on scale from 0 to 10 and a qualitative grade of {course_grade_qualitative}."
            }
        },
        "calculate_grades_context": true,
        "course_qualitative_grade": {
            "ranges": [
                {
                    "grade_text": "Insuficient",
                    "min_included": 0,
                    "max_excluded": 50
                },
                {
                    "grade_text": {
                        "pt-pt": "Regular",
                        "en": "Regular"
                    },
                    "min_included": 50,
                    "max_excluded": 65
                },
                {
                    "grade_text": {
                        "pt-pt": "Bom",
                        "en": "Good"
                    },
                    "min_included": 65,
                    "max_excluded": 80
                },
                {
                    "grade_text": {
                        "pt-pt": "Muito Bom",
                        "en": "Very Good"
                    },
                    "min_included": 80,
                    "max_excluded": 90
                },
                {
                    "grade_text": {
                        "pt-pt": "Excelente",
                        "en": "Excelent"
                    },
                    "min_included": 90,
                    "max_excluded": 101
                }
            ],
            "grade_round_format": "course_percent_grade:.0%"
        }
    },

    """
    grade_rounded = None
    try:
        grade_round_format = course_qualitative_grade_config.get("grade_round_format")

        # prefix with `{` if not already has that character
        if grade_round_format[0] != "{":
            grade_round_format = "{" + grade_round_format

        # suffix with `}` if not already has that character
        if grade_round_format[len(grade_round_format)-1] != "}":
            grade_round_format += "}"

        grade_rounded = grade_round_format.format(**context)
        # clear `%` caracter
        grade_rounded = grade_rounded.replace('%', '')
    except Exception:  # pylint: disable=broad-except
        log.error(
            "Could not round the course grade for qualitative grade scale for user %s in course %s",
            user.username,
            course.display_name,
        )

    # fall back
    if not grade_rounded:
        grade_rounded = context.course_percent_grade

    # append to context the rounded grade
    context.update({"course_grade_rounded" : grade_rounded})

    qualitative_grade = get_qualitative_grade(user, course, certificate_language, course_qualitative_grade_config.get("ranges", []), grade_rounded)
    if qualitative_grade:

        context.update({"course_grade_qualitative" : qualitative_grade})


def get_qualitative_grade(user, course, certificate_language, course_qualitative_ranges_settings, grade_rounded):
    """
    Returns a qualitative grade for the rounded grade given the course qualitative ranges settings.
    """
    try:
        grade_rounded_f = float(grade_rounded)
        for range in course_qualitative_ranges_settings:
            min_included = float(range.get("min_included", -1.0))
            max_excluded = float(range.get("max_excluded", -1.0))
            if min_included <= grade_rounded_f and grade_rounded_f < max_excluded:
                grade_text = range.get("grade_text", {})
                if type(grade_text) is dict:
                    # use certificate language to use correct grade text translation
                    grade_text = grade_text.get(certificate_language.lower())
                    if not grade_text:
                        # or use the default platform language
                        grade_text = grade_text.get(settings.LANGUAGE_CODE)
                else:
                    # if not a dict, probably it's already a string
                    grade_text = str(grade_text)
                if grade_text:
                    return grade_text
        log.warn(
            "Could not find any qualitative grade for user %s in course %s",
            user.username,
            course.display_name,
        )
        return None
    except Exception:  # pylint: disable=broad-except
        log.error(
            "Could not get qualitative grade for user %s in course %s with a rounded grade of %s",
            user.username,
            course.display_name,
            grade_rounded,
        )

def update_context_with_interpolated_strings(context, nau_cert_settings, certificate_language):
    """
    Updates certificate context using custom interpolated strings.
    Applies the corresponding translation before updating the context.
    """
    interpolated_strings = get_interpolated_strings(nau_cert_settings, certificate_language)

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


def get_interpolated_strings(nau_cert_settings, certificate_language):
    """
    Returns a dict with custom interpolated strings available for a certificate language.
    Returns an empty dict if it cant find a string for the given language.
    """
    lang_interpolated_strings = {}
    multilang_interpolated_strings = nau_cert_settings.get("interpolated_strings")
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
