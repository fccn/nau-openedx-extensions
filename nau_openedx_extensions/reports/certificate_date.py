"""
Certificate obtainment date column for the grade report.

Appends a ``certificate_obtained_date`` column to ``grade_report`` by wrapping
the platform's report write path, as decided for Phase 2
(fccn/nau-technical#955, request originally tracked in fccn/nau-technical#32):
NAU wants a real column inside ``grade_report`` — not a join with
``export_course_certificates``, and not a merge of the two reports.

The value is ``GeneratedCertificate.created_date`` (the same field the
``export_course_certificates`` report already publishes as
"certificate created date") in ISO 8601, and only for certificates in the
``downloadable`` status — the same condition behind the report's existing
"Certificate Delivered" column. Learners without a delivered certificate get
an empty cell.

Like the base-columns wrapper this is a monkeypatch (``instructor_task``
exposes no filter hook), installed once from ``AppConfig.ready()`` and inert
unless ``NAU_REPORTS_ENABLE_CERTIFICATE_DATE`` is ``True`` (default
``False``). ``tests/test_certificate_date.py`` is the conformance test that
detects silent breakage on upstream refactors.
"""

import csv
import logging
from functools import wraps
from tempfile import TemporaryFile

from django.conf import settings
from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)

HEADER = "certificate_obtained_date"
# The report whose rows get the column. The exact-match filter also keeps the
# companion error file (``grade_report_err``) untouched.
REPORT_NAME = "grade_report"
# Lowercased spellings of the username column: "Username" in the stock grade
# report, plus the identity column the base-columns wrapper may have already
# prepended by the time this wrapper runs.
USERNAME_ALIASES = {"username"}


def is_enabled():
    """
    Return whether the certificate-date column is enabled for this deployment.
    """
    return bool(getattr(settings, "NAU_REPORTS_ENABLE_CERTIFICATE_DATE", False))


def _as_course_key(course_id):
    """
    Return ``course_id`` as a CourseKey, accepting either a key or a string.
    """
    if isinstance(course_id, CourseKey):
        return course_id
    return CourseKey.from_string(str(course_id))


def _find_username_column(header):
    """
    Return the index of the username column in ``header``, or None.
    """
    for index, name in enumerate(header):
        if str(name).strip().lower() in USERNAME_ALIASES:
            return index
    return None


def _certificate_dates(course_key, usernames):
    """
    Map each username with a delivered certificate in the course to its
    ``created_date`` in ISO 8601. Usernames without one are left out.
    """
    # pylint: disable=import-error,import-outside-toplevel
    from lms.djangoapps.certificates.data import CertificateStatuses
    from lms.djangoapps.certificates.models import GeneratedCertificate

    certificates = GeneratedCertificate.objects.filter(
        course_id=course_key,
        status=CertificateStatuses.downloadable,
        user__username__in=set(usernames),
    ).values_list("user__username", "created_date")
    return {username: created.isoformat() for username, created in certificates}


def add_certificate_date(rows, course_key):
    """
    Return ``rows`` (header first) with the ``certificate_obtained_date``
    column appended. Rows without a delivered certificate get an empty cell.
    A report without a username column is returned unchanged.
    """
    header = list(rows[0])
    username_index = _find_username_column(header)
    if username_index is None:
        log.warning(
            "certificate_obtained_date: no username column in %s for %s; report left unchanged",
            REPORT_NAME,
            course_key,
        )
        return rows

    usernames = {
        str(row[username_index]) for row in rows[1:] if len(row) > username_index
    }
    dates = _certificate_dates(course_key, usernames)
    new_rows = [header + [HEADER]]
    for row in rows[1:]:
        row = list(row)
        username = str(row[username_index]) if len(row) > username_index else ""
        new_rows.append(row + [dates.get(username, "")])
    return new_rows


def _transform_csv_file(source, course_key):
    """
    Return a new temporary file with the ``certificate_obtained_date`` column
    appended to the CSV in ``source`` (a text-mode file positioned at the
    beginning).

    Two passes, like the base-columns transform: the first collects the
    usernames so the certificate dates come from one bulk query, the second
    writes the extended rows.
    """
    reader = csv.reader(source)
    try:
        header = next(reader)
    except StopIteration:
        source.seek(0)
        return source

    username_index = _find_username_column(header)
    if username_index is None:
        log.warning(
            "certificate_obtained_date: no username column in %s for %s; report left unchanged",
            REPORT_NAME,
            course_key,
        )
        source.seek(0)
        return source

    usernames = {row[username_index] for row in reader if len(row) > username_index}
    dates = _certificate_dates(course_key, usernames)
    source.seek(0)
    reader = csv.reader(source)
    next(reader)  # skip the header again

    output = TemporaryFile("r+", newline="", encoding="utf-8")
    writer = csv.writer(output)
    writer.writerow(header + [HEADER])
    for row in reader:
        username = row[username_index] if len(row) > username_index else ""
        writer.writerow(row + [dates.get(username, "")])
    output.seek(0)
    return output


def _wrap_rows(upload):
    """
    Wrap ``upload_csv_to_report_store`` so the grade report rows carry the
    certificate date column. This is the path ``CourseGradeReport`` actually
    uploads through (``InMemoryReportMixin._upload``).
    """
    if getattr(upload, "_nau_certificate_date", False):
        return upload

    @wraps(upload)
    def wrapper(rows, csv_name, course_id, timestamp, *args, **kwargs):
        rows = list(rows)
        if is_enabled() and csv_name == REPORT_NAME and rows:
            rows = add_certificate_date(rows, _as_course_key(course_id))
        return upload(rows, csv_name, course_id, timestamp, *args, **kwargs)

    wrapper._nau_certificate_date = True  # pylint: disable=protected-access
    return wrapper


def _wrap_file(upload):
    """
    Wrap ``upload_csv_file_to_report_store`` so the grade report carries the
    certificate date column.
    """
    if getattr(upload, "_nau_certificate_date", False):
        return upload

    @wraps(upload)
    def wrapper(file, csv_name, course_id, timestamp, *args, **kwargs):
        if is_enabled() and csv_name == REPORT_NAME:
            file = _transform_csv_file(file, _as_course_key(course_id))
        return upload(file, csv_name, course_id, timestamp, *args, **kwargs)

    wrapper._nau_certificate_date = True  # pylint: disable=protected-access
    return wrapper


def install():
    """
    Rebind the platform's upload helpers to the wrapping versions.

    Called once from ``AppConfig.ready()``; safe to call again (already
    wrapped functions are left untouched). ``CourseGradeReport`` uploads its
    rows through ``upload_csv_to_report_store`` in the ``grades`` namespace;
    the file-based helper is wrapped as well so a future upstream switch to
    the streamed path keeps the column (the conformance test pins which path
    is actually in use). ``utils`` is rebound for late importers.

    Composes with the base-columns wrapper regardless of install order: this
    transform appends its column at the end of the row, the base-columns one
    prepends at the front, and both locate the username column by name.
    """
    # pylint: disable=import-error,import-outside-toplevel
    from lms.djangoapps.instructor_task.tasks_helper import grades, utils

    for module in (utils, grades):
        module.upload_csv_to_report_store = _wrap_rows(module.upload_csv_to_report_store)
        module.upload_csv_file_to_report_store = _wrap_file(module.upload_csv_file_to_report_store)
    log.info("Grade report certificate-date wrapper installed (enabled=%s)", is_enabled())
