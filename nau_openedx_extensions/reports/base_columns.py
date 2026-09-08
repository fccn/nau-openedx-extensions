"""
Common base columns for every CSV course report (ADR 0001).

Prepends a common base structure to every CSV course report by wrapping the
platform's report write path:

- ``org_id``, ``course_id``, ``course_run`` on every CSV report;
- ``anonymous_user_id`` on learner-grain reports, i.e. reports whose header
  carries a username column under one of its known spellings (see
  ``LEARNER_KEY_ALIASES``). Course-grain reports (no learner column) get the
  course columns only; the learner column is omitted, never left empty.

This is a monkeypatch, because ``instructor_task`` exposes no filter hook.
Upgrade path: an openedx-filters step once one exists upstream.
``tests/test_base_columns.py`` is the conformance test that detects silent
breakage on upstream refactors — keep it passing on every platform upgrade.

The wrappers are installed once from ``AppConfig.ready()`` and stay inert
unless ``NAU_REPORTS_ENABLE_BASE_COLUMNS`` is ``True`` (default ``False``),
so rollback needs no code change.

``upload_zip_to_report_store`` is deliberately left unwrapped: ZIP archives
have no CSV header to extend (see the ADR).
"""

import csv
import logging
from functools import wraps
from tempfile import TemporaryFile

from django.conf import settings
from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)

COURSE_HEADERS = ["org_id", "course_id", "course_run"]
LEARNER_HEADER = "anonymous_user_id"
# Lowercased spellings of the learner column across the four target reports:
# student_profile_info -> "username", grade_report -> "Username",
# export_course_certificates -> "student username",
# course_survey_results -> "User Name".
LEARNER_KEY_ALIASES = {"username", "user name", "student username"}


def is_enabled():
    """
    Return whether the base-columns contract is enabled for this deployment.
    """
    return bool(getattr(settings, "NAU_REPORTS_ENABLE_BASE_COLUMNS", False))


def _as_course_key(course_id):
    """
    Return ``course_id`` as a CourseKey, accepting either a key or a string.
    """
    if isinstance(course_id, CourseKey):
        return course_id
    return CourseKey.from_string(str(course_id))


def _find_learner_column(header):
    """
    Return the index of the learner (username) column in ``header``, or None
    if the report carries no learner column (course grain).
    """
    for index, name in enumerate(header):
        if str(name).strip().lower() in LEARNER_KEY_ALIASES:
            return index
    return None


def _anonymous_id_map(usernames, course_key):
    """
    Map each username to its course-specific anonymous user id.

    Existing ids are fetched with a single bulk query, mirroring
    ``anonymous_id_for_user``'s read path (most recent row wins). Ids that do
    not exist yet are created through ``anonymous_id_for_user`` itself, so the
    result always matches what the platform would return. Usernames that do
    not resolve to a user (e.g. deleted accounts) are left out of the map and
    end up as an empty cell in the report.
    """
    # pylint: disable=import-error,import-outside-toplevel
    from common.djangoapps.student.models import AnonymousUserId, anonymous_id_for_user
    from django.contrib.auth import get_user_model

    usernames = set(usernames)
    mapping = {}
    existing = (
        AnonymousUserId.objects.filter(user__username__in=usernames, course_id=course_key)
        .select_related("user")
        .order_by("user_id", "-id")
    )
    for row in existing:
        # First row seen per user is the one with the highest id, which is
        # the one anonymous_id_for_user returns.
        mapping.setdefault(row.user.username, row.anonymous_user_id)

    missing = usernames - set(mapping)
    if missing:
        for user in get_user_model().objects.filter(username__in=missing):
            mapping[user.username] = anonymous_id_for_user(user, course_key)
    return mapping


def add_base_columns(rows, course_id):
    """
    Return ``rows`` (header first) with the base columns prepended.

    Learner-grain reports (header carries a username column) get
    ``org_id, course_id, course_run, anonymous_user_id``; course-grain
    reports get the course columns only.
    """
    course_key = _as_course_key(course_id)
    course_values = [course_key.org, str(course_key), course_key.run]
    header = list(rows[0])
    learner_index = _find_learner_column(header)

    if learner_index is None:
        new_rows = [COURSE_HEADERS + header]
        new_rows.extend(course_values + list(row) for row in rows[1:])
        return new_rows

    usernames = {
        str(row[learner_index]) for row in rows[1:] if len(row) > learner_index
    }
    anonymous_ids = _anonymous_id_map(usernames, course_key)
    new_rows = [COURSE_HEADERS + [LEARNER_HEADER] + header]
    for row in rows[1:]:
        row = list(row)
        username = str(row[learner_index]) if len(row) > learner_index else ""
        new_rows.append(course_values + [anonymous_ids.get(username, "")] + row)
    return new_rows


def _transform_csv_file(source, course_key):
    """
    Return a new temporary file with the base columns prepended to the CSV in
    ``source`` (a text-mode file positioned at the beginning).

    The file is processed line by line in two passes (the first collects the
    usernames so the anonymous-id map is built with a bulk query, the second
    writes the transformed rows), so the full report is never held in memory.
    """
    reader = csv.reader(source)
    try:
        header = next(reader)
    except StopIteration:
        source.seek(0)
        return source

    course_values = [course_key.org, str(course_key), course_key.run]
    learner_index = _find_learner_column(header)

    anonymous_ids = {}
    if learner_index is not None:
        usernames = {row[learner_index] for row in reader if len(row) > learner_index}
        anonymous_ids = _anonymous_id_map(usernames, course_key)
        source.seek(0)
        reader = csv.reader(source)
        next(reader)  # skip the header again

    output = TemporaryFile("r+", newline="", encoding="utf-8")
    writer = csv.writer(output)
    if learner_index is None:
        writer.writerow(COURSE_HEADERS + header)
        writer.writerows(course_values + row for row in reader)
    else:
        writer.writerow(COURSE_HEADERS + [LEARNER_HEADER] + header)
        for row in reader:
            username = row[learner_index] if len(row) > learner_index else ""
            writer.writerow(course_values + [anonymous_ids.get(username, "")] + row)
    output.seek(0)
    return output


def _wrap_rows(upload):
    """
    Wrap ``upload_csv_to_report_store`` so the rows carry the base columns.
    """
    if getattr(upload, "_nau_base_columns", False):
        return upload

    @wraps(upload)
    def wrapper(rows, csv_name, course_id, timestamp, *args, **kwargs):
        rows = list(rows)
        if is_enabled() and rows:
            rows = add_base_columns(rows, course_id)
        return upload(rows, csv_name, course_id, timestamp, *args, **kwargs)

    wrapper._nau_base_columns = True  # pylint: disable=protected-access
    return wrapper


def _wrap_file(upload):
    """
    Wrap ``upload_csv_file_to_report_store`` so the streamed CSV file carries
    the base columns.
    """
    if getattr(upload, "_nau_base_columns", False):
        return upload

    @wraps(upload)
    def wrapper(file, csv_name, course_id, timestamp, *args, **kwargs):
        if is_enabled():
            file = _transform_csv_file(file, _as_course_key(course_id))
        return upload(file, csv_name, course_id, timestamp, *args, **kwargs)

    wrapper._nau_base_columns = True  # pylint: disable=protected-access
    return wrapper


def install():
    """
    Rebind the platform's CSV upload helpers to the wrapping versions.

    Called once from ``AppConfig.ready()``; safe to call again (already
    wrapped functions are left untouched).

    The three report modules import the upload functions into their own
    namespace at import time, so each namespace is rebound individually.
    ``utils`` itself is rebound as well so that late importers — including
    this plugin's own ``edxapp_wrapper.backends.instructor_task_r_v1``, which
    is imported lazily on first use — also go through the wrapper.
    ``upload_zip_to_report_store`` is deliberately not wrapped.
    """
    # pylint: disable=import-error,import-outside-toplevel
    from lms.djangoapps.instructor_task.tasks_helper import enrollments, grades, misc, utils

    for module in (utils, enrollments, grades, misc):
        module.upload_csv_to_report_store = _wrap_rows(module.upload_csv_to_report_store)
    for module in (utils, grades):
        module.upload_csv_file_to_report_store = _wrap_file(module.upload_csv_file_to_report_store)
    log.info("Report base-columns wrapper installed (enabled=%s)", is_enabled())
