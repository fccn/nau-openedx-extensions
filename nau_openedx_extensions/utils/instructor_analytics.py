# -*- coding: utf-8 -*-
"""
Utilities for instructor analytics customization in NAU openedX extensions.
"""
from __future__ import absolute_import, unicode_literals

import logging

from django.conf import settings

from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings

logger = logging.getLogger(__name__)

# Course advanced setting key that lists extra student profile fields to include in
# the instructor Student Profile Info CSV report for a specific course.
_COURSE_SETTING_KEY = "nau_additional_features_on_instructor_analytics_student_profile_info"

# Django setting name for the global allowlist of all valid extra features.
_DJANGO_ALLOWLIST_SETTING = "NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO"


def get_student_features_with_custom_factory(prev_get_student_features_with_custom):
    """
    Factory function to wrap the get_student_features_with_custom function.

    This allows NAU to append additional student profile fields per-course from the
    course advanced setting ``nau_additional_features_on_instructor_analytics_student_profile_info``
    without exposing sensitive fields (e.g. VAT ID / NIF) by default.

    Two layers of configuration control which fields are appended:

    1. **Django allowlist** (``NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO``):
       A site-level list of *all* field names that are ever permitted to appear in the
       Student Profile Info CSV.  This guards against typos or misconfiguration at the
       course level.  Example Django setting::

           NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO = [
               "nau_nif",
               "nau_user_extended_model_cc_nic",
           ]

    2. **Course advanced setting** (``nau_additional_features_on_instructor_analytics_student_profile_info``):
       A per-course list that selects which of the allowed fields to activate for that
       specific course.  Only fields that also appear in the Django allowlist are included;
       any field not in the allowlist triggers a warning and is skipped.  Example::

           nau_additional_features_on_instructor_analytics_student_profile_info:
               ["nau_nif"]

    Behaviour:
    - The original ``get_student_features_with_custom(course_key)`` is called first so
      that the existing ``additional_student_profile_attributes`` site-configuration
      mechanism continues to work.
    - Course-level fields are filtered against the Django allowlist before being appended.
    - Duplicate entries are removed while preserving order.
    - A ``WARNING`` is logged for any course-level field not present in the allowlist.

    Args:
        prev_get_student_features_with_custom: The original ``get_student_features_with_custom``
            function from ``lms.djangoapps.instructor_analytics.basic``.

    Returns:
        A wrapped version of the function that includes NAU per-course extra fields.
    """

    def get_student_features_with_custom_wrapper(course_key):
        """
        Wraps the original get_student_features_with_custom to add NAU per-course extra fields.
        """
        # Step 1: delegate to the original function
        features = prev_get_student_features_with_custom(course_key)

        # Step 2: read the per-course advanced setting
        other_course_settings = get_other_course_settings(course_key)
        extra_features = other_course_settings.get("value", {}).get(_COURSE_SETTING_KEY, [])

        if not extra_features:
            return features

        # Step 3: validate the value is a list
        if not isinstance(extra_features, list):
            logger.warning(
                "Course other settings '%s' for course '%s' is not a list (got %s), ignoring.",
                _COURSE_SETTING_KEY, course_key, type(extra_features).__name__,
            )
            return features

        # Step 4: filter against the site-level Django allowlist
        allowlist = getattr(settings, _DJANGO_ALLOWLIST_SETTING, [])
        existing = set(features)
        new_fields = []
        for field in extra_features:
            if field not in allowlist:
                logger.warning(
                    "Field '%s' requested by course '%s' is not in the allowlist '%s', skipping.",
                    field, course_key, _DJANGO_ALLOWLIST_SETTING,
                )
            elif field not in existing:
                # Step 5: append only fields not already present
                new_fields.append(field)

        if new_fields:
            features = features + tuple(new_fields)

        return features

    return get_student_features_with_custom_wrapper
