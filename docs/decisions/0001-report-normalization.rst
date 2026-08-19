0001: Common Base Structure for All Course Reports
###############################################

Status
******

**Draft** *2026-08-14*

Scope: Phase 2 only, and within it only what report normalization means and how
it is built. Phase 1 (profile field collection) and Phase 3 (ZIP bundling) are
dependencies, not subjects.

Context
*******

Every course report defines its own columns independently. This causes three
problems.

**Course identity is not in the data.** It exists only in the file name,
``{org}_{course}_{run}_{report}_{timestamp}.csv``. To know which course run a
row belongs to, a consumer has to parse the file name.

**The same concept has different names.** The learner appears as ``Student ID``
in ``grade_report``, ``User ID`` in ``course_survey_results``, and ``id`` in
``student_profile_info``. Three naming styles are in use.

**Nobody has written down what a row is.** Most reports have one row per
learner per course run. But ``cohort_results`` has one row per cohort, and some
reports are ZIP archives with no rows at all.

The result is that joining two reports needs rules invented per report, and
cross-course analysis needs file-name parsing. FCCN has asked for a mandatory
base structure — Course ID, Course Run, Student/User ID, Org ID — in every
report, and has also asked whether a consolidated per-course "super-report" is
viable.

Decision
********

We define a base column contract, enforce it by wrapping the platform's report
write path from the plugin, and publish a report catalog describing every
report.

1. Reports declare their row grain
==================================

Two grains exist:

- **learner grain** — one row per learner per course run. Carries all base
  columns.
- **course grain** — one row about the course run itself. Carries the course
  columns; the learner column is omitted, not left empty.

ZIP reports have no rows. They are outside the column contract and normalize on
file naming only.

This is why the contract cannot simply be "four columns in every report".
``cohort_results`` has no learner to name. An empty column would look joinable
without being joinable.

2. The base columns
===================

.. code-block::

    org_id         FCT                             # course_key.org
    course_id      course-v1:FCT+CTC101x+2020_T2   # str(course_key)
    course_number  CTC101x                         # course_key.course
    course_run     2020_T2                         # course_key.run
    username       jdoe                            # learner grain only

The full opaque key is emitted next to its decomposed parts. It is the only
globally unique join key, and the decomposed fields are what people filter on.
Emitting both costs three columns and removes all parsing from the consumer.

Names are ``snake_case``, lowercase, English. No report header passes through
``gettext``, so column names are safe to treat as a machine contract.

``username`` is the learner key because it is the only identifier all four
target reports already carry. ``user.id`` is absent from
``export_course_certificates``, which iterates certificates and emits email,
username and name but never the id.

3. The columns are added by wrapping the platform's write path
==============================================================

All reports, native and custom, are written through three functions in
``lms/djangoapps/instructor_task/tasks_helper/utils.py``. Those functions
already receive the ``CourseKey``, so the course columns can be added there
without editing a single report.

We do not edit ``edx-platform``, and ``instructor_task`` offers no extension
point. The plugin therefore installs a wrapper at startup. See *Implementation*
below.

4. Base columns go first, and this is a breaking change
=======================================================

Consumers that read by column position will break. The change is announced with
a dated cutover and version 1 of the report catalog. It ships behind a plugin
setting that defaults to off, so rollback needs no code change.

5. Profile data without a recorded collection context is omitted
================================================================

This is deny-by-default. Recording that context is Phase 1 work; this ADR only
decides what the report does when it is missing.

6. The certificate issue date is delivered by a join, not a new column
======================================================================

Issue #32 asks for the certificate date in ``grade_report``. That value already
exists in ``export_course_certificates``. Once both reports carry the base
structure they join on ``course_id`` and ``username``, so the requirement is met
with no code.

This is the first demonstration of what normalization buys. The same argument
answers the "super-report" request: we deliver the join keys instead of the
join, and the partner builds any consolidation they need in their own analytical
layer.

Implementation
**************

The three report modules import the upload functions into their own namespace,
so the plugin rebinds them there from ``AppConfig.ready()``:

.. code-block:: python

    # nau_openedx_extensions/reports/base_columns.py
    #
    # ponytail: monkeypatch, because instructor_task exposes no filter hook.
    # Upgrade path: an openedx-filters step once one exists upstream.
    # test_base_columns.py is what detects breakage on upgrade.

    COURSE_HEADERS = ["org_id", "course_id", "course_number", "course_run"]
    LEARNER_KEY_ALIASES = {"username", "user name", "student username"}


    def _wrap_rows(upload):
        @wraps(upload)
        def wrapper(rows, csv_name, course_id, timestamp, *args, **kwargs):
            rows = list(rows)
            if _enabled() and rows:
                values = _course_values(course_id)
                rows = [COURSE_HEADERS + _normalize_header(rows[0])] + [
                    values + list(row) for row in rows[1:]
                ]
            return upload(rows, csv_name, course_id, timestamp, *args, **kwargs)

        return wrapper


    def install():
        """Called once from AppConfig.ready()."""
        from lms.djangoapps.instructor_task.tasks_helper import (
            enrollments, grades, misc,
        )

        for module in (enrollments, grades, misc):
            module.upload_csv_to_report_store = _wrap_rows(
                module.upload_csv_to_report_store
            )
        grades.upload_csv_file_to_report_store = _wrap_file(
            grades.upload_csv_file_to_report_store
        )

Large grade reports are streamed to a temporary file instead of built as a row
list. For those, ``_wrap_file`` prepends a CSV-escaped constant prefix to each
line, so the report is never re-parsed.

``upload_zip_to_report_store`` is deliberately left unwrapped.

NAU custom reports need no patching. They already import these functions through
``edxapp_wrapper``.

Renaming the learner key
========================

The wrapper sees the header row, so it also renames the learner key through the
alias map. The value is already present in all four target reports, only the
name differs:

.. code-block::

    student_profile_info         username           # already correct
    grade_report                 Username
    export_course_certificates   student username
    course_survey_results        User Name

Because of this, no report needs to be edited to satisfy the contract. The whole
normalization is one module and one test.

Two adjustments are still required
==================================

- ``export_course_certificates`` already emits its own ``course_id`` column.
  Once the wrapper adds the base structure, the file would carry that header
  twice. The report is NAU-owned, so its own column is dropped. This must land
  in the same change as the wrapper.
- ``student_profile_info`` builds its header from
  ``student_profile_download_fields``, a site configuration value that
  *replaces* the default field list. A deployment configured without
  ``username`` would silently stop satisfying the contract, so the conformance
  test must cover that case.

The conformance test
====================

One test runs each report generator and asserts its leading columns. It is
mandatory, not optional: the wrapper is a monkeypatch, and this test is the only
thing that detects an upstream rename during an upgrade. Without it, reports
would keep generating, silently missing the base structure.

Consequences
************

- Every CSV grows by four to five columns.
- Consumers reading by column position break at the cutover. Consumers mapping
  by header name are unaffected.
- Every Open edX upgrade must run the conformance test before release.
- Cross-report joins no longer need file-name parsing, and cross-course
  aggregation needs no further platform work.
- Learners who registered before Phase 1 records a collection context will lose
  their profile columns, unless a backfill is agreed. FCCN needs to hear this
  before seeing it in a report.
- The report catalog becomes a deliverable: per report, its name, row grain,
  base fields, full column list, and the variables that still require
  partner-side inference.

Dependencies
************

These are not solved by the column contract.

**The platform's report listing ignores** ``parent_dir``.
``ReportStore.links_for()`` resolves its path without it, so a report written to
a custom directory disappears from the Data Download listing. Until the plugin
has its own listing endpoint, ``parent_dir`` stays unused.

**Verawood removes the instructor dashboard tab mechanism.** The NAU area today
is ``FilterCertificateExportTab``, a template fragment rendered through
``InstructorDashboardRenderStarted``. Anything built as a template tab has an
expiry date. The listing should therefore be built as a REST endpoint that the
current tab consumes now and an MFE slot consumes later. That endpoint also
resolves the ``parent_dir`` limitation above, and it is the architectural
recommendation FCCN asked for as a Phase 2 deliverable.

**Profile data has no collection context.** ``NauUserExtendedModel`` is a
``OneToOneField`` on the user, so profile answers are global. Until Phase 1
records where each answer was collected, the column set of
``student_profile_info`` cannot be frozen.

Rejected Alternatives
*********************

**Editing the write path in** ``edx-platform``. Simplest technically. Rejected
because all work stays in the plugin, and it would fork a file that changes
every release.

**A custom storage class via** ``GRADES_DOWNLOAD.STORAGE_CLASS``. Configuration
only, no patching. Rejected because the course key cannot be recovered at that
layer: the directory is ``sha1(course_id)``, and the file name separates on
``_`` while org and run legitimately contain underscores, as in ``2020_T2``.

**Editing every report individually.** N changes, N upstream reviews, and every
future upstream report escapes the contract silently.

**Post-processing stored files.** Doubles I/O and adds a failure mode after the
report has been reported as complete.

**A learner column in every report, empty where undefined.** Produces columns
that look joinable and are not.

**Renaming all legacy headers.** Breaks every consumer at once and forks files
that change every release. We rename only the learner key, which is the column
the contract depends on.

**Building a consolidated "super-report".** Different row grains would duplicate
or drop rows. Grade reports have a per-course variable column count, so the
consolidated schema would differ per course, which is the opposite of
normalization. It would also cost the heaviest report plus the join on every
request.

Open Questions
**************

**Where do the reports live?** The scope email says the survey report goes in
"the same reporting area instructors already use". The issue's acceptance
criteria call for a dedicated NAU area with a different name. If reports stay in
the standard listing, ``parent_dir`` is unused and the listing work shrinks to
the post-Verawood recommendation alone. *This has the largest effect on effort.*

**Does "Course ID" mean the full opaque key or the course number?** We emit
both; a confirmation would let us drop one.

**Is** ``username`` **acceptable under GDPR?** Technically it is settled. The
question is whether joins should run on the course-specific anonymous id
instead, with identity confined to ``student_profile_info``.

**Does ARTE map columns by header name or by position?** This decides whether
the change is a release note or a dated cutover.

**Is a three-field base structure accepted for course-grain reports?**

**Is a backfill of profile collection context required for existing learners?**

**Is the certificate date acceptable as a join, or must it be a real column?**

**Is "join keys instead of a super-report" accepted?**

References
**********

- Issue: `ARTE Reports - phase 2 <https://github.com/fccn/nau-technical/issues/955>`_,
  parent `#936 <https://github.com/fccn/nau-technical/issues/936>`_
- Related: `#791 <https://github.com/fccn/nau-technical/issues/791>`_,
  `#788 <https://github.com/fccn/nau-technical/issues/788>`_,
  `#796 <https://github.com/fccn/nau-technical/issues/796>`_,
  `#32 <https://github.com/fccn/nau-technical/issues/32>`_,
  `#735 <https://github.com/fccn/nau-technical/issues/735>`_
- Code: ``lms/djangoapps/instructor_task/tasks_helper/utils.py``,
  ``lms/djangoapps/instructor_task/models.py``,
  ``nau_openedx_extensions/edxapp_wrapper/backends/instructor_task_r_v1.py``,
  ``nau_openedx_extensions/filters/pipeline.py``,
  ``nau_openedx_extensions/certificate_export/management/commands/export_course_certificates.py``
