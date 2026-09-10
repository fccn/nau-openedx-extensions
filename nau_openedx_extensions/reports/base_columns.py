"""
Common base columns for every CSV course report.

Prepends a common identity block to every CSV course report by wrapping the
platform's report write path, matching the Phase 2 standardization NAU asked
for (fccn/nau-technical#955):

- ``course_id`` on every CSV report;
- ``email``, ``username``, ``student_id`` on learner-grain reports, i.e.
  reports whose header carries a username column under one of its known
  spellings (see ``LEARNER_KEY_ALIASES``). Course-grain reports (no learner
  column) get ``course_id`` only; the learner columns are omitted, never left
  empty.

This is a monkeypatch, because ``instructor_task`` exposes no filter hook.
The lasting landing is upstream (edx-platform); this plugin delivery is the
Phase 2 ship vehicle. ``tests/test_base_columns.py`` is the conformance test
that detects silent breakage on upstream refactors.

The wrappers are installed once from ``AppConfig.ready()`` and stay inert
unless ``NAU_REPORTS_ENABLE_BASE_COLUMNS`` is ``True`` (default ``False``),
so rollback needs no code change.

``upload_zip_to_report_store`` is deliberately left unwrapped: ZIP archives
have no CSV header to extend.
"""

import csv
import logging
from functools import wraps
from tempfile import TemporaryFile

from django.conf import settings
from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)

COURSE_HEADERS = ["course_id"]
LEARNER_HEADERS = ["email", "username", "student_id"]
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


def _learner_map(usernames):
    """
    Map each username to ``[email, username, student_id]``.

    Usernames that do not resolve to a user (e.g. deleted accounts) are left
    out of the map; the caller fills email and student_id with empty cells
    and keeps the username from the row.
    """
    # pylint: disable=import-outside-toplevel
    from django.contrib.auth import get_user_model

    mapping = {}
    for user in get_user_model().objects.filter(username__in=set(usernames)).only(
        "id", "username", "email"
    ):
        mapping[user.username] = [user.email or "", user.username, str(user.id)]
    return mapping


def _learner_values(username, learners):
    """
    Return ``[email, username, student_id]`` for ``username``.
    """
    return learners.get(username, ["", username, ""])


def add_base_columns(rows, course_id):
    """
    Return ``rows`` (header first) with the base columns prepended.

    Learner-grain reports (header carries a username column) get
    ``course_id, email, username, student_id``; course-grain reports get
    ``course_id`` only.
    """
    course_key = _as_course_key(course_id)
    course_values = [str(course_key)]
    header = list(rows[0])
    learner_index = _find_learner_column(header)

    if learner_index is None:
        new_rows = [COURSE_HEADERS + header]
        new_rows.extend(course_values + list(row) for row in rows[1:])
        return new_rows

    usernames = {
        str(row[learner_index]) for row in rows[1:] if len(row) > learner_index
    }
    learners = _learner_map(usernames)
    new_rows = [COURSE_HEADERS + LEARNER_HEADERS + header]
    for row in rows[1:]:
        row = list(row)
        username = str(row[learner_index]) if len(row) > learner_index else ""
        new_rows.append(course_values + _learner_values(username, learners) + row)
    return new_rows


def _transform_csv_file(source, course_key):
    """
    Return a new temporary file with the base columns prepended to the CSV in
    ``source`` (a text-mode file positioned at the beginning).

    The file is processed line by line in two passes (the first collects the
    usernames so the learner map is built with a bulk query, the second writes
    the transformed rows), so the full report is never held in memory.
    """
    reader = csv.reader(source)
    try:
        header = next(reader)
    except StopIteration:
        source.seek(0)
        return source

    course_values = [str(course_key)]
    learner_index = _find_learner_column(header)

    learners = {}
    if learner_index is not None:
        usernames = {row[learner_index] for row in reader if len(row) > learner_index}
        learners = _learner_map(usernames)
        source.seek(0)
        reader = csv.reader(source)
        next(reader)  # skip the header again

    output = TemporaryFile("r+", newline="", encoding="utf-8")
    writer = csv.writer(output)
    if learner_index is None:
        writer.writerow(COURSE_HEADERS + header)
        writer.writerows(course_values + row for row in reader)
    else:
        writer.writerow(COURSE_HEADERS + LEARNER_HEADERS + header)
        for row in reader:
            username = row[learner_index] if len(row) > learner_index else ""
            writer.writerow(course_values + _learner_values(username, learners) + row)
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
