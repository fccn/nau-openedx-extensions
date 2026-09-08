# -*- coding: utf-8 -*-
"""
Utilities for instructor analytics customization in NAU openedX extensions.

Implements fccn/nau-technical#797: allow segmenting the columns exported on the
Student Profile Info CSV per course, so that sensitive fields (e.g. VAT ID/NIF)
are only included for the subset of courses that need them.

This is a port to ``nau/teak.master`` of the design from
fccn/nau-openedx-extensions#135 (author: Ivo Branco). The original targeted
``get_additional_student_profile_attributes``, a function that only exists on
the platform fork after fccn/openedx-platform#38; on Teak that refactor is not
available, so this port injects the extra fields at the report task instead
(``upload_students_csv``), which needs no edx-platform change at all.
"""
from __future__ import absolute_import, unicode_literals

import logging
from functools import wraps

from django.conf import settings

from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings

logger = logging.getLogger(__name__)

# Course advanced setting key that lists extra student profile fields to include in
# the instructor Student Profile Info CSV report for a specific course.
_COURSE_SETTING_KEY = "nau_additional_features_on_instructor_analytics_student_profile_info"

# Django setting name for the global allowlist of all valid extra features.
_DJANGO_ALLOWLIST_SETTING = "NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO"


def get_nau_additional_course_features(course_key):
    """
    Return the extra student profile fields configured for a course.

    Two layers of configuration control which fields are returned:

    1. **Django allowlist** (``NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO``):
       A site-level list of *all* field names that are ever permitted to appear in the
       Student Profile Info CSV. This guards against typos or misconfiguration at the
       course level. Example Django setting::

           NAU_ALL_ADDITIONAL_FEATURES_ON_INSTRUCTOR_ANALYTICS_STUDENT_PROFILE_INFO = [
               "nau_nif",
               "nau_user_extended_model_cc_nic",
           ]

    2. **Course advanced setting** (``nau_additional_features_on_instructor_analytics_student_profile_info``):
       A per-course list (Studio > Settings > Advanced Settings > Other course settings)
       that selects which of the allowed fields to activate for that specific course.
       Only fields that also appear in the Django allowlist are included; any field not
       in the allowlist triggers a warning and is skipped. Example::

           nau_additional_features_on_instructor_analytics_student_profile_info:
               ["nau_nif"]

    Fields listed in the platform setting ``PROFILE_INFORMATION_REPORT_PRIVATE_FIELDS``
    are never returned: a field marked private site-wide cannot be re-enabled per course.

    Args:
        course_key: The course key to read the advanced setting for.

    Returns:
        list: validated extra field names, in course-setting order, deduplicated.
    """
    other_course_settings = get_other_course_settings(course_key)
    extra_features = other_course_settings.get("value", {}).get(_COURSE_SETTING_KEY, [])

    if not extra_features:
        return []

    if not isinstance(extra_features, list):
        logger.warning(
            "Course other settings '%s' for course '%s' is not a list (got %s), ignoring.",
            _COURSE_SETTING_KEY, course_key, type(extra_features).__name__,
        )
        return []

    allowlist = getattr(settings, _DJANGO_ALLOWLIST_SETTING, [])
    private_fields = getattr(settings, "PROFILE_INFORMATION_REPORT_PRIVATE_FIELDS", [])
    features = []
    for field in extra_features:
        if field not in allowlist:
            logger.warning(
                "Field '%s' requested by course '%s' is not in the allowlist '%s', skipping.",
                field, course_key, _DJANGO_ALLOWLIST_SETTING,
            )
        elif field in private_fields:
            logger.warning(
                "Field '%s' requested by course '%s' is marked private in "
                "'PROFILE_INFORMATION_REPORT_PRIVATE_FIELDS', skipping.",
                field, course_key,
            )
        elif field not in features:
            features.append(field)

    return features


def upload_students_csv_factory(prev_upload_students_csv):
    """
    Factory that wraps ``upload_students_csv`` to append NAU per-course extra fields.

    ``upload_students_csv`` is the instructor task that generates the Student
    Profile Info CSV; it receives the column list in ``task_input["features"]``
    (built by the instructor API view from the ``student_profile_download_fields``
    and ``additional_student_profile_attributes`` site configurations). This
    wrapper appends the fields selected by the course advanced setting — see
    ``get_nau_additional_course_features`` for the validation layers — before
    delegating to the original task. Fields already present are not duplicated.

    Extraction needs no further patching: ``enrolled_students_features`` resolves
    any non-profile feature with ``getattr`` on the User model, which is how the
    NAU extended-model attributes (e.g. ``nau_nif``) are already exposed.

    Args:
        prev_upload_students_csv: The original ``upload_students_csv`` function
            from ``lms.djangoapps.instructor_task.tasks_helper.enrollments``.

    Returns:
        A wrapped version of the task function.
    """

    @wraps(prev_upload_students_csv)
    def upload_students_csv_wrapper(_xblock_instance_args, _entry_id, course_id, task_input, action_name):
        """
        Wraps the original upload_students_csv to add NAU per-course extra fields.
        """
        extra_features = get_nau_additional_course_features(course_id)

        if extra_features:
            features = list(task_input.get("features") or [])
            new_fields = [field for field in extra_features if field not in features]
            if new_fields:
                task_input = dict(task_input, features=features + new_fields)
                logger.info(
                    "Appended extra student profile fields %s for course '%s'.",
                    new_fields, course_id,
                )

        return prev_upload_students_csv(_xblock_instance_args, _entry_id, course_id, task_input, action_name)

    upload_students_csv_wrapper._nau_additional_course_features = True  # pylint: disable=protected-access
    return upload_students_csv_wrapper


def install_upload_students_csv_wrapper():
    """
    Rebind ``upload_students_csv`` behind the NAU per-course extra fields wrapper.

    The name must be rebound in two modules:

    - ``lms.djangoapps.instructor_task.tasks_helper.enrollments``, where it is defined;
    - ``lms.djangoapps.instructor_task.tasks``, which imports it *by name* at module
      load and calls it through its own global namespace.

    Installation is idempotent, and a no-op outside the LMS (e.g. CMS) where the
    instructor task modules are not importable.
    """
    try:
        from lms.djangoapps.instructor_task import tasks  # pylint: disable=import-outside-toplevel
        from lms.djangoapps.instructor_task.tasks_helper import \
            enrollments  # pylint: disable=import-outside-toplevel
    except ImportError:
        logger.info("Instructor task modules unavailable; NAU profile columns wrapper not installed.")
        return

    for module in (enrollments, tasks):
        current = getattr(module, "upload_students_csv", None)
        if current is None or getattr(current, "_nau_additional_course_features", False):
            continue
        module.upload_students_csv = upload_students_csv_factory(current)

    logger.info("NAU per-course student profile fields wrapper installed.")
