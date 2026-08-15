0001: Common Base Structure for All Course Reports
###############################################

Status
******

**Draft** *2026-08-14*

Scope
*****

Phase 2 (DRC) only, and within it only what report normalization means and how
it is implemented.

- **Here:** the base column contract and where it is enforced; the report
  catalog; the reporting area's delivery mechanism, including the
  post-Verawood direction Phase 2 asks for.
- **Phase 2, decided elsewhere:** permissions for custom reports (#735 — an
  authorization fix, not a normalization decision); the survey report's own
  design (this ADR fixes only the columns it must carry).
- **Out:** Phase 1 (which profile fields are collected, and how the collection
  context is recorded — a dependency here, not a subject); Phase 3 (ZIP
  bundling); cross-course aggregation and partner-side inference.

Context
*******

Each report defines its own header list independently. Course identity exists
only in the file name (``{org}_{course}_{run}_{report}_{timestamp}.csv``), never
in the data. The same concept is named ``Student ID``, ``User ID`` or ``id``
across three naming styles. Row grain — what one row represents — is documented
nowhere. Joining two reports therefore needs per-report rules re-derived by
hand, and cross-course analysis needs file-name parsing.

FCCN confirmed the base structure (Course ID, Course Run, Student/User ID, Org
ID) for **all** existing reports, and asked whether a consolidated per-course
"super-report" is viable.

Three facts about the code shape the solution:

1. **There is a single write path.** Every report, native and custom, is
   persisted through ``upload_csv_to_report_store`` (row list),
   ``upload_csv_file_to_report_store`` (streamed temp file) or
   ``upload_zip_to_report_store`` (binary), in
   ``lms/djangoapps/instructor_task/tasks_helper/utils.py``. NAU custom reports
   reach them through ``nau_openedx_extensions/edxapp_wrapper``.
2. **The course keys are available there; the learner key is not.** Those
   functions receive ``course_id`` as a ``CourseKey`` (``.org``, ``.course``,
   ``.run``). The learner identifier is per-row data.
3. **Not every report has learner rows.** ``cohort_results`` is one row per
   cohort with no user identity; ZIP reports have no rows at all.

Two constraints bound the solution space. All work stays in
``nau-openedx-extensions``; ``edx-platform`` is not modified unless strictly
necessary. And the platform offers no extension point — ``instructor_task``
exposes no ``openedx_filters`` hook of any kind.

Constraints this ADR does not remove
====================================

**C1 —** ``ReportStore.links_for()`` **resolves its path without**
``parent_dir``, so reports written to a custom directory vanish from the Data
Download listing. *Blocks* grouping non-native reports into their own area.
*Owner:* Phase 2, decision 8. *Resolving it delivers* a plugin-owned listing
endpoint that reads any directory. Until it exists, ``parent_dir`` stays unused.

**C2 —** ``student_profile_info`` **cannot decide its own column set.**
``NauUserExtendedModel`` is a ``OneToOneField`` on the user, so profile answers
are global with no record of the course or org they were collected under.
*Blocks* freezing that report's column list. *Owner:* recording the context is
**Phase 1**; the behaviour in its absence is decision 9 below. *Resolving it
delivers* a profile report safe to hand to any instructor without a per-course
review.

**C3 — Verawood removes the instructor dashboard tab mechanism.** The NAU area
today is ``FilterCertificateExportTab``, rendering a template fragment through
``InstructorDashboardRenderStarted``. *Blocks* nothing today, but puts an expiry
on anything built as a template tab. *Owner:* Phase 2, decision 8. *Resolving it
delivers* a listing that survives the migration with only its presentation
rewritten.

Decision
********

Normalization means a **column contract defined per row grain**, enforced by
wrapping the shared write path from the plugin, and documented in a catalog.

**1. Two scopes, not the same list.** The *target catalog* is what NAU delivers
(8 → 4 reports). The *column contract* covers all existing reports. They do not
compete in cost: the course fields are injected once (point 3), so reports
outside the catalog are covered by the contract, not by a work item.

**2. Two row grains, and every report declares one.** ``learner x course run``
carries the full base structure; ``course`` carries the course fields only, and
the learner column is omitted rather than emitted empty. ZIP reports are outside
the column contract and normalize on file naming only.

**3. The base columns.**

.. code-block::

    org_id         FCT                             # course_key.org
    course_id      course-v1:FCT+CTC101x+2020_T2   # str(course_key)
    course_number  CTC101x                         # course_key.course
    course_run     2020_T2                         # course_key.run
    username       jdoe                            # learner grain only

The full opaque key is emitted alongside its decomposed parts: it is the only
globally unique join key, while the decomposed fields are what humans filter on.
Names are ``snake_case``, lowercase, English — safe as a machine contract, since
no report header passes through ``gettext``.

**4. Injection is a wrapper installed by the plugin at startup.** The three
report modules bind the upload functions into their own namespace at import
time, so the plugin rebinds them there from ``AppConfig.ready()``:

.. code-block:: python

    # nau_openedx_extensions/reports/base_columns.py
    #
    # ponytail: monkeypatch, because instructor_task exposes no filter hook.
    # Upgrade path: an openedx-filters step once one exists upstream (point 7).
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

For the streamed variant, ``_wrap_file`` wraps the file in a view that prepends
a CSV-escaped constant prefix to every line, so the report is never re-parsed.
That is a correctness and speed argument, not a memory one: ``store()`` already
does ``buff.read()`` on the whole file.

``upload_zip_to_report_store`` is deliberately left unwrapped.

NAU custom reports need no patching — they already import through
``edxapp_wrapper``, their legitimate injection point.

**5. The wrapper also renames the learner key**, via the alias map above. This
is what makes the fourth field achievable without editing any report: the value
is already present in every learner-grain report, only its column name differs.
Consequently **the whole normalization is one module plus one test**, and
per-report work for the target catalog is close to zero.

The ceiling is stated openly: a monkeypatch breaks silently if upstream renames
those modules, changes the import style, or adds a fourth report module.

**6. Base columns are prepended, and the change is breaking.** Consumers reading
by column position break at the cutover, announced with version 1 of the
catalog. The behaviour ships behind a plugin setting, defaulting to off — a
rollback that needs no code change.

**7. Upstream is a follow-up, not the delivery vehicle.** What NAU proposes
upstream is an **extension point** — a filter on report upload, in an area that
has none — so the monkeypatch can be retired. Delivery does not wait for it.

**8. The reporting area is delivered as an API first, a tab second.** The
current tab launches tasks but does not list reports, so a listing must be built
regardless. It is implemented as a REST endpoint in the plugin honouring
``parent_dir`` (resolving C1); the existing tab consumes it today, an MFE slot
consumes it after Verawood (resolving C3). The architectural recommendation FCCN
asked for is then a description of what was built, not a separate study.

**9. Profile data with no recorded collection context is omitted**, consistent
with deny-by-default. Recording the context is Phase 1; this is only the
report's behaviour in its absence.

**10. One conformance test asserts the leading columns of every report.** Under
point 4 it is also the only detector of a monkeypatch upstream has invalidated,
so it is mandatory. It runs in the plugin's suite against the pinned platform
version.

**11. The certificate issue date is delivered by the join, not a new column.**
Issue #32's value already exists in ``export_course_certificates`` as
``certificate created date``. Once both reports carry the base structure they
join on ``course_id`` plus the learner key, and the requirement is met with no
code. If the column must be physically inside ``grade_report``, the route is a
small upstream contribution to ``_user_certificate_info`` — not a plugin patch,
since the grade report's internal header and row builders change shape between
releases while the upload signature does not.

**12. The report catalog is a deliverable:** per report, name, row grain, base
fields, full column list, and the variables still requiring partner-side
inference (for example "course status", which has no single native field).

Consequences
************

- Every CSV grows by four to five columns.
- Consumers reading by column position break at the cutover; those mapping by
  header name are unaffected.
- NAU carries a startup monkeypatch against three upstream namespaces — one
  plugin file, gated by a setting, covered by the conformance test. Every Open
  edX upgrade must run that test before release: an upstream rename disables
  the injection silently, and reports keep generating without the base
  structure.
- Cross-report joins stop needing file-name parsing; cross-course aggregation
  needs no further platform work.
- Reports must not move into the NAU area before the listing endpoint exists.
- Deny-by-default has a visible effect: learners who registered before Phase 1
  records a collection context lose their profile columns unless a backfill is
  agreed. FCCN must hear this before discovering it in a report.
- ZIP *bundling* (Phase 3) is not the same subject as reports that already are
  ZIP archives; the two should not be conflated in planning.

Rejected Alternatives
*********************

- **Editing the shared write path in** ``edx-platform``. Simplest technically;
  rejected on the standing constraint, and it would fork a file that changes
  every release.
- **A custom storage class via** ``GRADES_DOWNLOAD.STORAGE_CLASS``.
  Configuration only, no patching — but the course key is not recoverable
  there: the directory is ``sha1(course_id)`` and the file name separates on
  ``_`` while org and run legitimately contain underscores (``2020_T2``).
  Injecting columns would mean guessing course identity from a filename.
- **Editing every report individually.** N changes, N upstream reviews, and
  every future upstream report escapes the contract silently.
- **Post-processing stored files.** Doubles I/O and adds a failure mode after
  the report is already reported complete.
- **A learner column everywhere, empty where undefined.** Produces columns that
  look joinable and are not.
- **Renaming all legacy headers.** Full consistency, but breaks every consumer
  at once and forks files that change every release. Point 5 renames only the
  learner key, which is the one the contract depends on.
- **Building a consolidated "super-report".** Different row grains would
  duplicate or drop rows; grade reports have a per-course variable column count,
  so the consolidated schema would differ per course — the opposite of
  normalization; and it would cost the heaviest report plus the join on every
  request. The base structure delivers the join keys instead of the join, which
  is the intended answer to the consolidation request.

Open Questions
**************

- The scope email says the survey report goes in "the same reporting area
  instructors already use", while the issue's acceptance criteria call for a
  dedicated NAU area with a different name. Which one? If reports stay in the
  standard listing, ``parent_dir`` is unused and point 8 shrinks to the
  post-Verawood recommendation alone. **Largest effect on effort.**
- Does "Course ID" mean the full opaque key or the course number? Point 3 emits
  both; confirmation would let us drop one.
- Is ``username`` acceptable as the learner key under GDPR, or should joins run
  on the course-specific anonymous id, with identity confined to
  ``student_profile_info``?
- Does ARTE ingestion map columns by header name or by position? This decides
  whether point 6 is a release note or a dated cutover.
- Is a three-field base structure accepted for course-grain reports?
- Is a backfill of profile collection context required for existing learners?
- Is the certificate date acceptable as a join, or must it be a physical column?
- Is "join keys instead of a super-report" accepted?

References
**********

- Issue: `ARTE Reports - phase 2 <https://github.com/fccn/nau-technical/issues/955>`_ ·
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
