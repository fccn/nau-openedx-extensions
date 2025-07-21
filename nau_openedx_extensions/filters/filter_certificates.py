"""
Certificate-related filters.

This module contains all filters related to certificate processing and
customization in Open edX. The implemented filters allow modifying the
certificate rendering context, adding custom user profile data, calculating
grades, and adding custom interpolated strings.

Available filters:

- FilterUpdateCertificateContext: Updates the certificate context with extended
  user profile data, course grades, and custom strings.
"""

import logging
from typing import Any

from crum import get_current_request
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import translation
from django.utils.translation import gettext as _
from opaque_keys.edx.keys import CourseKey
from openedx_filters import PipelineStep

from nau_openedx_extensions.edxapp_wrapper.certificates import (
    CertificateHtmlViewConfiguration,
    GeneratedCertificate,
    get_catalog_data_for_course,
    get_custom_template_and_language,
)
from nau_openedx_extensions.edxapp_wrapper.course_module import get_course
from nau_openedx_extensions.edxapp_wrapper.grades import get_course_grades

log = logging.getLogger(__name__)


class FilterUpdateCertificateContext(PipelineStep):
    """
    Update the certificate context with the user's extended profile fields.

    This filter enhances the certificate rendering process by adding user profile data,
    course grades, and custom interpolated strings to the certificate context.

    Example usage:

    Add the following configurations to your configuration file:

        ```
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.certificate.render.started.v1": {
                "fail_silently": False,
                "pipeline": [
                    "nau_openedx_extensions.filters.filter_certificates.FilterUpdateCertificateContext"
                ]
            }
        }
        ```
    """

    def run_filter(self, context, custom_template) -> dict[str, Any]:  # pylint: disable=arguments-differ
        """
        Update the certificate context with the user's extended profile fields.

        Args:
            context (dict): The certificate context to be updated.
            custom_template (Any): The custom template to be used for certificate rendering.

        Returns:
            dict[str, Any]: Updated context dictionary containing the modified context.
        """
        # pylint: disable=import-outside-toplevel
        from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel

        properties = self._get_properties(context, custom_template)

        # Update context with custom form data
        self._update_context_with_custom_form(properties["user"], NauUserExtendedModel, context)

        if properties["nau_cert_settings"]:
            self._update_context_with_grades(
                properties["user"],
                properties["course"],
                context,
                properties["nau_cert_settings"],
                properties["user_certificate"],
                properties["certificate_language"],
            )
            self._update_context_with_interpolated_strings(
                context, properties["nau_cert_settings"], properties["certificate_language"]
            )

        return {"context": context}

    def _get_properties(self, context: dict[str, Any], custom_template: Any) -> dict[str, Any]:
        """
        Extract and prepare all necessary properties for certificate context processing.

        Args:
            context (dict[str, Any]): The current certificate context.
            custom_template (Any): The custom template configuration.

        Returns:
            dict[str, Any]: Dictionary containing all necessary properties:
                - certificate_language: Language to use for certificate
                - configuration: Certificate HTML view configuration
                - course: Course object
                - course_key: Course key object
                - nau_cert_settings: Custom certificate settings
                - request: Current HTTP request
                - user: User object
                - user_certificate: Generated certificate for the user
        """
        course_key = CourseKey.from_string(context["course_id"])
        course = get_course(course_key)
        request = get_current_request()
        user = request.user  # type: ignore
        user_certificate = GeneratedCertificate.objects.get(user=user, course_id=course.id)
        certificate_language = self._determine_certificate_language(course, user_certificate, custom_template)

        return {
            "certificate_language": certificate_language,
            "configuration": CertificateHtmlViewConfiguration.get_config(),
            "course": course,
            "course_key": course_key,
            "nau_cert_settings": course.cert_html_view_overrides.get("nau_certs_settings"),
            "request": request,
            "user": user,
            "user_certificate": user_certificate,
        }

    def _determine_certificate_language(self, course, user_certificate, custom_template: Any) -> str:
        """
        Determine the appropriate language for the certificate.

        Args:
            course (CourseBlock): Course object.
            user_certificate (GeneratedCertificate): Generated certificate object.
            custom_template (Any): Custom template configuration.

        Returns:
            str: Language code to use for the certificate.
        """
        user_language = translation.get_language()

        if not custom_template:
            return user_language

        catalog_data = get_catalog_data_for_course(course.id)
        _, custom_template_language = get_custom_template_and_language(
            course.id, user_certificate.mode, catalog_data.pop("content_language", None)
        )

        return custom_template_language or user_language

    def _update_context_with_custom_form(self, user, custom_model: Any, context: dict[str, Any]) -> None:
        """
        Update the context with custom user form data from the extended profile model.

        Extracts Boolean, CharField, and TextField data from the user's extended profile
        model and adds them to the certificate context.

        Args:
            user (User): The user object whose profile data will be added.
            custom_model (Any): The custom model class containing extended user data.
            context (dict[str, Any]): The context dictionary to update in-place.
        """
        try:
            custom_model_instance = custom_model.objects.get(user=user)
        except ObjectDoesNotExist:
            # If a custom model does not exist for the user, create an empty one
            custom_model_instance = custom_model()

        for field in custom_model_instance._meta.fields:
            if isinstance(field, (models.BooleanField, models.CharField, models.TextField)):
                context_element = {field.name: getattr(custom_model_instance, field.name, "")}
                context.update(context_element)

    def _update_context_with_grades(
        self,
        user,
        course,
        context: dict[str, Any],
        nau_certs_settings: dict[str, Any],
        user_certificate,
        certificate_language: str,
    ) -> None:
        """
        Update certificate context with grades data for the user.

        Adds the user's certificate grade and optionally calculates additional grade
        information based on course settings, including letter grades, percentage grades,
        and qualitative grade scales.

        Args:
            user (User): The user object for whom grades are being calculated.
            course (CourseBlock): The course object containing grade settings.
            context (dict[str, Any]): The context dictionary to update in-place.
            nau_certs_settings (dict[str, Any]): Custom certificate settings from course.
            user_certificate (GeneratedCertificate): The generated certificate for the user.
            certificate_language (str): Language code for the certificate.
        """
        # always add `user certificate` grade context
        context.update({"certificate_final_grade": user_certificate.grade})

        if nau_certs_settings.get("calculate_grades_context", False):
            try:
                grades = get_course_grades(user, course)
                # The `grades.percent` is a number from 0 to 1.
                grade_percent = grades.percent
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
                self._course_qualitative_grade(
                    user,
                    course,
                    context,
                    course_qualitative_grade_config,
                    certificate_language,
                )

    def _course_qualitative_grade(
        self,
        user,
        course,
        context: dict[str, Any],
        course_qualitative_grade_config: dict[str, Any],
        certificate_language: str,
    ) -> None:
        """
        Generate and add qualitative grade information to the certificate context.

        Formats the grade according to course-specific rounding configuration and
        determines the corresponding qualitative grade based on defined ranges.

        Args:
            user (User): The user object for whom the grade is being calculated.
            course (CourseBlock): The course object containing grade settings.
            context (dict[str, Any]): The context dictionary to update in-place.
            course_qualitative_grade_config (dict[str, Any]): Configuration for qualitative grading.
            certificate_language (str): Language code for the certificate.

        Example:

        ```
        "nau_certs_settings": {
            "interpolated_strings": {
                "accomplishment_copy_course_description": {
                    "pt": ", com nota de numérica de {course_percent_grade:.0%} numa escala de"
                        " 0 a 10 e nota qualitativa de {course_grade_qualitative}.",
                    "en": ", with a numberic grade of {course_percent_grade:.0%} on scale from"
                        " 0 to 10 and a qualitative grade of {course_grade_qualitative}.",
                }
            },
            "calculate_grades_context": True,
            "course_qualitative_grade": {
                "ranges": [
                    {
                        "grade_text": "Insuficient",
                        "min_included": 0,
                        "max_excluded": 50,
                    },
                    {
                        "grade_text": {"pt-pt": "Regular", "en": "Regular"},
                        "min_included": 50,
                        "max_excluded": 65,
                    },
                    {
                        "grade_text": {"pt-pt": "Bom", "en": "Good"},
                        "min_included": 65,
                        "max_excluded": 80,
                    },
                    {
                        "grade_text": {"pt-pt": "Muito Bom", "en": "Very Good"},
                        "min_included": 80,
                        "max_excluded": 90,
                    },
                    {
                        "grade_text": {"pt-pt": "Excelente", "en": "Excelent"},
                        "min_included": 90,
                        "max_excluded": 101,
                    },
                ],
                "grade_round_format": "course_percent_grade:.0%",
            },
        }
        ```
        """
        grade_rounded = None
        try:
            grade_round_format = course_qualitative_grade_config.get("grade_round_format")

            # prefix with `{` if not already has that character
            if grade_round_format and grade_round_format[0] != "{":
                grade_round_format = "{" + grade_round_format

            # suffix with `}` if not already has that character
            if grade_round_format and grade_round_format[len(grade_round_format) - 1] != "}":
                grade_round_format += "}"

            if grade_round_format:
                grade_rounded = grade_round_format.format(**context)
                # clear `%` character
                grade_rounded = grade_rounded.replace("%", "")
        except Exception:  # pylint: disable=broad-except
            log.error(
                "Could not round the course grade for qualitative grade scale for user %s in course %s",
                user.username,
                course.display_name,
            )

        # fall back
        if not grade_rounded:
            grade_rounded = str(context.get("course_percent_grade", 0))

        # append to context the rounded grade
        context.update({"course_grade_rounded": self._format_grade(grade_rounded, certificate_language)})

        qualitative_grade = self._get_qualitative_grade(
            user,
            course,
            certificate_language,
            course_qualitative_grade_config.get("ranges", []),
            grade_rounded,
        )
        if qualitative_grade:
            context.update({"course_grade_qualitative": qualitative_grade})

    def _format_grade(self, grade: str, language: str) -> str:
        """
        Format grade according to language-specific conventions.

        For Portuguese language, replaces decimal dots with commas to match
        local number formatting conventions.

        Args:
            grade (str): The grade value to format.
            language (str): The language code for formatting.

        Returns:
            str: The formatted grade string.
        """
        if language[:2] == "pt":
            return str(grade).replace(".", ",")
        return str(grade)

    def _get_qualitative_grade(
        self,
        user,
        course,
        certificate_language: str,
        course_qualitative_ranges_settings: list[dict[str, Any]],
        grade_rounded: str,
    ) -> str | None:
        """
        Determine the qualitative grade based on numeric grade and configured ranges.

        Maps the rounded grade to a qualitative description (e.g., "Excellent", "Good")
        based on the course's qualitative grade range settings. Supports multi-language
        grade text configurations.

        Args:
            user (User): The user object for logging purposes.
            course (CourseBlock): The course object for logging purposes.
            certificate_language (str): Language code for selecting appropriate grade text.
            course_qualitative_ranges_settings (list[dict[str, Any]]): List of grade ranges
                with their corresponding qualitative descriptions.
            grade_rounded (str): The rounded numeric grade as a string.

        Returns:
            str | None: The qualitative grade text, or None if no matching range is found
                or if an error occurs.
        """
        try:
            grade_rounded_f = float(grade_rounded)
            for qualitative_range in course_qualitative_ranges_settings:
                min_included = float(qualitative_range.get("min_included", -1.0))
                max_excluded = float(qualitative_range.get("max_excluded", -1.0))
                if min_included <= grade_rounded_f < max_excluded:
                    grade_text = qualitative_range.get("grade_text", {})
                    if isinstance(grade_text, dict):
                        # use certificate language to use correct grade text translation
                        grade_text_dict = grade_text
                        grade_text = grade_text_dict.get(certificate_language.lower())
                        if not grade_text:
                            # or use the default platform language
                            grade_text = grade_text_dict.get(settings.LANGUAGE_CODE)
                    else:
                        # if not a dict, probably it's already a string
                        grade_text = str(grade_text)
                    if grade_text:
                        return grade_text
            log.warning(
                "Could not find any qualitative grade for user %s in course %s",
                user.username,
                course.display_name,
            )
        except Exception:  # pylint: disable=broad-except
            log.exception(
                "Could not get qualitative grade for user %s in course %s with a rounded grade of %s",
                user.username,
                course.display_name,
                grade_rounded,
            )
        return None

    def _update_context_with_interpolated_strings(
        self, context: dict[str, Any], nau_cert_settings: dict[str, Any], certificate_language: str
    ) -> None:
        """
        Update certificate context with custom interpolated strings.

        Retrieves custom interpolated strings for the certificate language, applies
        translations, formats them with context variables, and adds them to the
        certificate context.

        Args:
            context (dict[str, Any]): The context dictionary to update in-place.
            nau_cert_settings (dict[str, Any]): Custom certificate settings containing
                interpolated strings configuration.
            certificate_language (str): Language code for selecting appropriate strings.
        """
        interpolated_strings = self._get_interpolated_strings(nau_cert_settings, certificate_language)

        if interpolated_strings:
            for key, value in interpolated_strings.items():
                try:
                    # Also try to translate the string if defined in platform .po
                    formatted_string = _(value).format(**context)  # pylint: disable=translation-of-non-string
                except (ValueError, AttributeError, KeyError):
                    log.error("Failed to add value (%s) as formatted string in the certificate context", value)
                    continue
                else:
                    context.update({key: formatted_string})

    def _get_interpolated_strings(self, nau_cert_settings: dict[str, Any], certificate_language: str) -> dict[str, Any]:
        """
        Extract custom interpolated strings for the specified certificate language.

        Searches through the multi-language interpolated strings configuration and
        returns strings that match the certificate language.

        Args:
            nau_cert_settings (dict[str, Any]): Custom certificate settings containing
                interpolated strings configuration.
            certificate_language (str): Language code to match against string configurations.

        Returns:
            dict[str, Any]: Dictionary of custom interpolated strings for the language,
                or empty dict if no strings are found for the specified language.
        """
        lang_interpolated_strings = {}
        multilang_interpolated_strings = nau_cert_settings.get("interpolated_strings")
        if multilang_interpolated_strings:
            for key, value in multilang_interpolated_strings.items():
                try:
                    for lang, string in value.items():
                        if lang in certificate_language:
                            lang_interpolated_strings[key] = string
                            break
                except AttributeError:
                    log.error("Failed to read (%s) as formatted string in the certificate context", key)
                    continue

        return lang_interpolated_strings
