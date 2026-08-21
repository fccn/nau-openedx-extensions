0001: Common Base Structure for All Course Reports
###############################################

Status
******

**Draft** *2026-08-20*

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
report.

Decision
********

We define a base column contract, enforce it by wrapping the platform's report
write path from the plugin, and publish a report catalog describing every
report.

1. Reports declare their row grain
==================================

Two grains exist:

- **learner grain** — one row per learner per course run. Example:
  ``grade_report``, one row per enrolled learner. Carries all base columns.
- **course grain** — one row about the course run itself, or an aggregate over
  it. Example: ``cohort_results``, one row per cohort, describing how many
  learners were added to it. Carries the course columns only; the learner
  column is omitted, not left empty.

ZIP reports are a third case. ``export_course_certificates_pdfs`` and
``submission_files`` are archives of binary files, so there is no CSV header to
add columns to. They already carry ``{org}_{course}_{run}`` in their file name,
and that is all the normalization they get.

This is why the contract cannot simply be "four columns in every report".
``cohort_results`` has no single learner to name, so a learner column there
would have to be empty. An empty column looks joinable without being joinable,
which is worse for the consumer than an honest omission.

2. The base columns
===================

.. code-block::

    org_id             FCT                             # course_key.org
    course_id          course-v1:FCT+CTC101x+2020_T2   # str(course_key)
    course_run         2020_T2                         # course_key.run
    anonymous_user_id  a3f1c9...                       # learner grain only

``course_id`` is the full course key string. It is the only globally unique join
key. ``course_run`` is emitted separately because filtering and grouping by run
is the common case and should not require parsing.

Names are ``snake_case``, lowercase, English. No report header passes through
``gettext``, so column names are safe to treat as a machine contract.

3. The learner key is the course-specific anonymous ID, not the username
========================================================================

Usernames are personally identifiable information under GDPR. A join key is
copied into every report and travels to the partner's analytical systems, so it
is the worst place to put PII.

The platform already provides a suitable key. ``anonymous_id_for_user(user,
course_id)`` returns a stable per-(user, course) identifier, persisted in
``AnonymousUserId``, designed for exactly this purpose. It is unique, stable
across report runs, and carries no identity on its own.

Alternatives considered:

- ``username`` — the only identifier all four target reports already carry, so
  it is the cheapest option. Rejected: it is PII, and it is also mutable, since
  learners can be renamed.
- ``user.id`` — stable, but re-identifying, meaningless to the partner, and
  absent from ``export_course_certificates``, which emits email, username and
  name but never the id.

This decision does **not** remove existing identity columns. Reports that
already carry ``Username`` or ``Email`` keep them; whether an individual report
may expose identity is a GDPR scoping question per report, not part of this
contract. What changes is only which column the partner joins on.

The wrapper still needs a learner column to resolve, and ``username`` is the one
column all four target reports already have. It is used as the lookup input, not
published as the key. See *Implementation*.

4. The columns are added by wrapping the platform's write path
==============================================================

All reports, native and custom, are written through three functions in
``lms/djangoapps/instructor_task/tasks_helper/utils.py``. Those functions
already receive the ``CourseKey``, so the course columns can be added there
without editing a single report.

We do not edit ``edx-platform``, and ``instructor_task`` offers no extension
point. The plugin therefore installs a wrapper at startup. See *Implementation*
below.

5. Base columns go first
========================

Consumers that read by column position will break. This is a new feature
affecting every report, so the release is a major version bump regardless, and
the change is announced with version 1 of the report catalog. It ships behind a
plugin setting that defaults to off, so rollback needs no code change.

6. Profile data without a recorded collection context is omitted
================================================================

*Collection context* means the course and organization a learner was in when
they answered a profile question. NAU collects profile fields at registration,
inside a specific course and org, and GDPR requires that the answer only be used
in that context.

Example: a learner enrols in a course of **org X** and provides their NIF during
registration. If that same learner later enrols in a course of **org Y**, the
NIF must not appear in org Y's ``student_profile_info`` report, because it was
never collected for org Y.

Today nothing records that context, so this ADR fixes the safe behaviour: **when
no collection context is recorded for a profile answer, the column is omitted.**
That is deny-by-default. Recording the context is Phase 1 work; this ADR only
decides what the report does while it is missing.

Note this is about *profile* columns only. The base structure itself, and the
report's own columns such as grades or enrolment status, are unaffected.

7. The certificate issue date is delivered by a join, not a new column
======================================================================

`Issue #32 <https://github.com/fccn/nau-technical/issues/32>`_ asks for the
certificate issue date in ``grade_report``. That value already exists as
``certificate created date`` in ``export_course_certificates``, which is a
NAU-owned report.

Once both reports carry the base structure, they join on ``course_id`` and
``anonymous_user_id``:

.. code-block::

    grade_report                 org_id  course_id  course_run  anonymous_user_id  Grade  ...
    export_course_certificates   org_id  course_id  course_run  anonymous_user_id  certificate created date  ...

So the requirement is met with no code. This is the concrete payoff of the base
structure: values that live in different reports become combinable without a
new report being built for each combination.

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

    COURSE_HEADERS = ["org_id", "course_id", "course_run"]
    LEARNER_HEADER = "anonymous_user_id"
    LEARNER_KEY_ALIASES = {"username", "user name", "student username"}


    def _wrap_rows(upload):
        @wraps(upload)
        def wrapper(rows, csv_name, course_id, timestamp, *args, **kwargs):
            rows = list(rows)
            if _enabled() and rows:
                rows = _add_base_columns(rows, course_id)
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
list. For those, ``_wrap_file`` applies the same transformation line by line, so
the report is never re-parsed.

``upload_zip_to_report_store`` is deliberately left unwrapped.

NAU custom reports need no patching. They already import these functions through
``edxapp_wrapper``.

Resolving the anonymous ID
==========================

The wrapper reads the header row and looks for a learner column using the alias
map. The value is already present in all four target reports, under four
different names:

.. code-block::

    student_profile_info         username
    grade_report                 Username
    export_course_certificates   student username
    course_survey_results        User Name

If a learner column is found, the report is learner grain, and the wrapper
resolves each username to ``anonymous_id_for_user(user, course_id)``. The
mapping is built once per report with a single query over the course's enrolled
users, not once per row.

If no learner column is found, the report is course grain and only the course
columns are added.

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
  ``username`` would leave the wrapper with no learner column to resolve, and
  the report would silently drop to course grain. The conformance test must
  cover that case.

The conformance test
====================

A new test in the plugin, ``tests/test_base_columns.py``. For each report
generator it runs the report against a small fixture course and asserts three
things:

1. the first columns of the output are exactly ``COURSE_HEADERS``, with the
   course's own values;
2. learner-grain reports carry ``anonymous_user_id`` next, matching
   ``anonymous_id_for_user`` for that learner;
3. course-grain reports carry no learner column at all.

It is mandatory, not optional. The wrapper is a monkeypatch, so this test is the
only thing that detects an upstream rename during an Open edX upgrade. Without
it, reports would keep generating and silently lose the base structure.

Consequences
************

- Every CSV grows by three to four columns.
- Consumers reading by column position break at the release that lands this.
  Consumers mapping by header name are unaffected.
- Every Open edX upgrade must run the conformance test before release.
- Cross-report joins no longer need file-name parsing, and cross-course
  aggregation needs no further platform work.
- The partner joins on an anonymous ID, so cross-report analysis no longer
  requires handling personal data.
- Learners whose profile answers predate Phase 1 recording a collection context
  have no context on those answers. Under decision 6 those columns are omitted,
  so ``student_profile_info`` will show fewer profile fields for them than it
  does today. Either a backfill rule is agreed, or FCCN accepts the loss. This
  needs to be said before it is discovered in a report.
- The report catalog becomes a deliverable: per report, its name, row grain,
  base fields, full column list, and the variables that still require
  partner-side inference.

Dependencies
************

These are not solved by the column contract.

**The platform's report listing ignores** ``parent_dir``.
``ReportStore.links_for()`` resolves its path without it, so a report written to
a custom directory would disappear from the Data Download listing. *Today this
has no consequence*: no NAU report passes ``parent_dir``, so every report is
listed normally. It only becomes a problem if we move reports into a separate
directory, which decision below defers.

**Verawood removes the instructor dashboard tab mechanism.** The NAU area today
is ``FilterCertificateExportTab``, a template fragment rendered through
``InstructorDashboardRenderStarted``. Anything built as a template tab has an
expiry date.

We therefore do **not** build a separate reporting area or listing endpoint now.
Reports stay in the standard Data Download listing, ``parent_dir`` stays unused,
and where reports should live is decided by the Verawood migration plan, which
is the Phase 2 deliverable FCCN asked for. Building a listing today would be
significant work for little immediate gain, and it would be rewritten anyway if
Verawood centralizes reporting itself — which the migration plan must confirm.

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
that change every release. The wrapper adds columns and does not rename existing
ones.

Open Questions
**************

**Does ARTE map columns by header name or by position?** Position-mapping
consumers break when the base columns are added, so this determines what
migration support the partner needs.

**Is a three-field base structure accepted for course-grain reports?** Reports
like ``cohort_results`` describe a cohort, not a learner, so they can carry
``org_id``, ``course_id`` and ``course_run`` but no learner key.

**Is a backfill of profile collection context required for existing learners**,
or is the reduced ``student_profile_info`` output acceptable for them?

**Is the certificate issue date acceptable as a join with**
``export_course_certificates``, or must it be a real column inside
``grade_report``?

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
  ``common/djangoapps/student/models/user.py`` — ``anonymous_id_for_user``,
  ``nau_openedx_extensions/edxapp_wrapper/backends/instructor_task_r_v1.py``,
  ``nau_openedx_extensions/filters/pipeline.py``,
  ``nau_openedx_extensions/certificate_export/management/commands/export_course_certificates.py``
