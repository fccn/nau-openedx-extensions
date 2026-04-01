"""
Signal handlers for course_filters.

Connects to the internal CMS course_published signal so that
NauCourseFilter rows are kept in sync whenever a course is saved
in Studio (including Advanced Settings saves).
"""

import logging

from nau_openedx_extensions.course_filters.sync import sync_course_filters_for_course

log = logging.getLogger(__name__)


def course_published_handler(course_key, **kwargs):  # pylint: disable=unused-argument
    """
    Handler for the CMS course_published signal.

    Syncs NauCourseFilter rows for the published course. Wrapped in a broad
    try/except so this handler never raises and never blocks the course
    publishing flow.
    """
    try:
        log.info("course_filters: received course_published signal for %s", course_key)
        result = sync_course_filters_for_course(course_key)
        log.info(
            "course_filters: sync completed for %s — created=%d, deleted=%d, unchanged=%d",
            course_key,
            result["created"],
            result["deleted"],
            result["unchanged"],
        )
    except Exception:  # pylint: disable=broad-except
        log.exception("course_filters: unexpected error in course_published_handler for %s", course_key)
