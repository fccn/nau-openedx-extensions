"""
Sync logic for NauCourseFilter.

This module is the single source of truth for reading other_course_settings
from MongoDB and writing the active filters to MySQL. It is used by both the
course_published signal handler (per-course, on save) and the backfill
management command (all courses, on demand).
"""

import logging

from django.conf import settings

from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings

log = logging.getLogger(__name__)

# Default filter keys to track. Extend via settings.NAU_COURSE_FILTER_KEYS.
_DEFAULT_FILTER_KEYS = (
    "filter_enrollment_by_domain_list",
    "filter_enrollment_require_nif",
    "certificate_require_portuguese_citizen_card",
)


def get_known_filter_keys():
    """Return the tuple of filter keys to track, from settings or defaults."""
    return tuple(getattr(settings, "NAU_COURSE_FILTER_KEYS", _DEFAULT_FILTER_KEYS))


def sync_course_filters_for_course(course_key):
    """
    Synchronize NauCourseFilter rows for a single course.

    Reads other_course_settings from MongoDB, determines which known filter
    keys have a truthy value, then:
    - creates rows for newly active filters,
    - deletes rows for filters that are no longer active.

    Returns a dict with keys 'created', 'deleted', 'unchanged' counts.
    Raises no exceptions — errors are logged so callers (e.g. signal handlers)
    are never blocked.
    """
    from nau_openedx_extensions.course_filters.models import NauCourseFilter  # pylint: disable=import-outside-toplevel

    course_id_str = str(course_key)
    result = {"created": 0, "deleted": 0, "unchanged": 0}

    try:
        other_course_settings = get_other_course_settings(course_key)
        settings_values = other_course_settings.get("value", {})

        known_keys = get_known_filter_keys()
        active_filters = {key for key in known_keys if settings_values.get(key)}

        existing_qs = NauCourseFilter.objects.filter(course_id=course_id_str)
        existing_filters = set(existing_qs.values_list("filter_type", flat=True))

        to_create = active_filters - existing_filters
        to_delete = existing_filters - active_filters

        if to_create:
            NauCourseFilter.objects.bulk_create(
                [NauCourseFilter(course_id=course_id_str, filter_type=ft) for ft in to_create]
            )
            result["created"] = len(to_create)
            log.info("course_filters: created %d filter(s) for %s: %s", len(to_create), course_id_str, to_create)

        if to_delete:
            deleted_count, _ = existing_qs.filter(filter_type__in=to_delete).delete()
            result["deleted"] = deleted_count
            log.info("course_filters: deleted %d filter(s) for %s: %s", deleted_count, course_id_str, to_delete)

        result["unchanged"] = len(active_filters & existing_filters)

    except Exception:  # pylint: disable=broad-except
        log.exception("course_filters: error syncing filters for course %s", course_id_str)

    return result
