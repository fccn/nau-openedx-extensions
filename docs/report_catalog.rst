==================
Report Catalog v1
==================

:Status: Draft — v1, matches the base-columns implementation on Open edX Teak
:Reference: ``docs/decisions/0001-report-normalization.rst`` (ADR 0001)

This catalog is the deliverable defined by ADR 0001: for every CSV course
report it lists the report name, its row grain, the base fields it carries,
its full column list, and the variables that still require partner-side
inference.

It covers every report written through the platform report store
(``upload_csv_to_report_store`` / ``upload_csv_file_to_report_store``), which
is the write path wrapped by ``nau_openedx_extensions.reports.base_columns``.
All of them are downloaded from the instructor dashboard (*Data Download*
listing), except the NAU certificate export, which has its own tab today.

The base-columns contract
=========================

With ``NAU_REPORTS_ENABLE_BASE_COLUMNS = True`` (default: ``False``), every
report below is prepended with:

.. list-table::
   :header-rows: 1
   :widths: 22 20 58

   * - Column
     - Applies to
     - Value
   * - ``org_id``
     - every report
     - organization code, e.g. ``FCT``
   * - ``course_id``
     - every report
     - full course key, e.g. ``course-v1:FCT+Course+2026``
   * - ``course_run``
     - every report
     - the run part of the course key, e.g. ``2026``
   * - ``anonymous_user_id``
     - learner-grain reports only
     - course-scoped anonymous id of the learner in that row

*Row grain* is the meaning of one row. A report is **learner grain** when each
row belongs to an identifiable learner — detected through a learner column
whose header is ``username``, ``user name`` or ``student username``
(case-insensitive). Reports without such a column receive only the three
course columns.

Until the release that enables the flag, consumers that read columns by
position keep working unchanged; after it, consumers must map columns by
header name. Joins across reports of the same course use
``anonymous_user_id``; joins across courses use ``course_id``/``org_id``.
None of the CSVs carry course metadata (course name, start/end dates):
deriving them stays on the consumer side, joining ``course_id`` against the
course catalog.

Catalog
=======

grade_report
------------

- **File name:** ``{course_prefix}_grade_report_{timestamp}.csv`` (errors, if
  any, in ``…_grade_report_err_…``)
- **Generator:** ``CourseGradeReport`` (``lms/djangoapps/instructor_task/tasks_helper/grades.py``)
- **Row grain:** learner (one row per enrolled learner)
- **Base fields:** ``org_id``, ``course_id``, ``course_run``, ``anonymous_user_id``
- **Columns:** ``Student ID``, ``Email``, ``Username``, ``Grade``, one column
  per graded assignment/subsection (course-dependent), then, when the course
  uses the feature: ``Cohort Name``, ``Experiment Group (…)``, ``Team Name``;
  always: ``Enrollment Track``, ``Verification Status``, ``Certificate
  Eligible``, ``Certificate Delivered``, ``Certificate Type``, ``Enrollment
  Status``.
- **Partner-side inference:** the assignment columns vary per course, so any
  cross-course aggregation must map them by name; pass/fail interpretation
  requires the course grading policy (not in the CSV).

problem_grade_report
--------------------

- **File name:** ``{course_prefix}_problem_grade_report_{timestamp}.csv``
- **Generator:** ``ProblemGradeReport`` (same module)
- **Row grain:** learner
- **Base fields:** all four
- **Columns:** ``Student ID``, ``Email``, ``Username``, ``Enrollment
  Status``, ``Grade``, then one *(Earned, Possible)* column pair per gradable
  block (course-dependent).
- **Partner-side inference:** same caveat as ``grade_report`` for the
  per-block columns.

student_profile_info — entry open
---------------------------------

- **File name:** ``{course_prefix}_student_profile_info_{timestamp}.csv``
- **Generator:** ``upload_students_csv`` (``enrollments.py``)
- **Row grain:** learner
- **Base fields:** all four
- **Columns:** configured per deployment through the
  ``student_profile_download_fields`` site configuration. NAU currently
  configures: ``id``, ``username``, ``name``, ``email``, ``language``,
  ``location``, ``year_of_birth``, ``gender``, ``level_of_education``,
  ``enrollment_mode``, ``last_login``, ``date_joined``, ``enrollment_date``,
  ``nau_user_extended_model_cc_nic``, ``nau_nif``,
  ``nau_user_extended_model_employment_situation``,
  ``nau_user_extended_model_nuts``, ``nau_user_extended_model_cae4``.
- **Partner-side inference:** age (from ``year_of_birth``); NUTS region and
  CAE4 sector labels (the CSV carries the codes).
- **Note:** per ADR 0001 this entry **stays open** until the profile scoping
  conflict is settled (whether extended-profile columns are global or
  per-course/organization). The column set cannot be frozen before that.

may_enroll_info
---------------

- **File name:** ``{course_prefix}_may_enroll_info_{timestamp}.csv``
- **Generator:** ``upload_may_enroll_csv`` (``enrollments.py``)
- **Row grain:** invited email address (people allowed to enroll who have not
  registered yet — no user account exists)
- **Base fields:** course columns only. There is no learner column and no
  account to anonymize, so ``anonymous_user_id`` does not apply.
- **Columns:** ``email``.

course_survey_results
---------------------

- **File name:** ``{course_prefix}_course_survey_results_{timestamp}.csv``
- **Generator:** ``upload_course_survey_report`` (``misc.py``); only exists
  for courses using the platform survey tool.
- **Row grain:** learner
- **Base fields:** all four (the ``User Name`` header is recognized as the
  learner column)
- **Columns:** ``User ID``, ``User Name``, ``Email``, then one column per
  survey field (course-dependent).
- **Note:** this is the upstream survey tool. The NAU survey report from the
  proposal is a separate deliverable, pending NAU's decision on the source
  data — see *Reserved entries* below.

proctored_exam_results_report
-----------------------------

- **File name:** ``{course_prefix}_proctored_exam_results_report_{timestamp}.csv``
- **Generator:** ``upload_proctored_exam_results_report`` (``misc.py``)
- **Row grain:** exam attempt (learner-resolvable: carries ``username``)
- **Base fields:** all four
- **Columns:** ``course_id``, ``provider``, ``track``, ``exam_name``,
  ``username``, ``email``, ``attempt_code``, ``allowed_time_limit_mins``,
  ``is_sample_attempt``, ``started_at``, ``completed_at``, ``status``,
  ``review_status``, ``Suspicious Count``, ``Suspicious Comments``,
  ``Rules Violation Count``, ``Rules Violation Comments``.
- **Note:** this report has its own legacy ``course_id`` column; with the flag
  on, the value is duplicated by the base column. Harmless for name-based
  consumers; kept as-is in v1.

cohort_results
--------------

- **File name:** ``{course_prefix}_cohort_results_{timestamp}.csv``
- **Generator:** ``upload_students_to_cohorts`` result summary (``misc.py``)
- **Row grain:** cohort (course grain)
- **Base fields:** course columns only
- **Columns:** ``Cohort Name``, ``Exists``, ``Learners Added``, ``Learners
  Not Found``, ``Invalid Email Addresses``, ``Preassigned Learners``.

ORA_data / ORA_summary
----------------------

- **File names:** ``{course_prefix}_ORA_data_{timestamp}.csv`` and
  ``{course_prefix}_ORA_summary_{timestamp}.csv``
- **Generator:** ``upload_ora2_data`` / ``upload_ora2_summary`` (``misc.py``),
  columns produced by the ``openassessment`` app.
- **Row grain:** submission / learner-assessment summary. The headers are
  produced by the ORA app and identify learners by ORA's own anonymized
  student id, not by a ``username`` column.
- **Base fields:** course columns only (no recognized learner column).
- **Partner-side inference:** ORA's anonymized id is the same course-scoped
  anonymous id used by ``anonymous_user_id``, so rows can be joined against
  learner-grain reports through it.

problem_responses
-----------------

- **File name:** derived from the selected problem location(s) and filters
  (dynamic), one CSV per request.
- **Generator:** ``ProblemResponses`` (``grades.py``)
- **Row grain:** learner response (learner-resolvable: carries ``username``)
- **Base fields:** all four
- **Columns:** ``username``, ``title``, ``location``, then dynamic columns
  depending on the problem type (state, answers, attempts…).

anonymized_ids
--------------

- **File name:** ``{course_prefix}_anonymized_ids_{timestamp}.csv``
- **Generator:** ``generate_anonymous_ids`` (``misc.py``)
- **Row grain:** learner, but identified by numeric ``User ID`` — there is no
  ``username`` column.
- **Base fields:** course columns only.
- **Columns:** ``User ID``, ``Anonymized User ID``, ``Course Specific
  Anonymized User ID``.
- **Note:** ``Course Specific Anonymized User ID`` here is the same value the
  contract exposes as ``anonymous_user_id`` on learner-grain reports. This
  report exists precisely to let staff map ids and therefore contains
  re-identifiable data; handle accordingly.

export_course_certificates (NAU)
--------------------------------

- **File name:** ``{course_prefix}_export_course_certificates_{timestamp}.csv``
- **Generator:** ``export_course_certificates`` management command /
  certificate-export tab (this plugin)
- **Row grain:** issued certificate (learner-resolvable: carries ``student
  username``)
- **Base fields:** all four
- **Columns (flag on):** ``student email``, ``student username``, ``student
  name``, ``certificate created date``, ``certificate verify_uuid``,
  ``certificate_web_link_url``, ``certificate_download_pdf_link``. The
  report's own legacy ``course_id`` column (previously the first one) is
  dropped because the base column replaces it.
- **Columns (flag off, legacy):** ``course_id`` followed by the same columns.
- **Open point:** NAU has not yet decided whether the certificate *issue
  date* consumers need is ``certificate created date`` as a real column
  (current state) or a join through ``anonymous_user_id``. The entry may gain
  or rename a date column when that is settled.

Reserved entries
================

- **NAU survey report** — required by the proposal; pending NAU's decision on
  the source data. Its entry (name, grain, columns) will be added when the
  source is settled. It will follow the same contract (learner grain expected).

Out of scope of the contract
============================

These downloads do not go through the wrapped CSV write path, so they carry no
base columns:

- ``issued_certificates.csv`` — synchronous HTTP response from the instructor
  dashboard, never stored in the report store.
- ORA submission files / attachments archives and certificate PDF archives —
  ZIP files, uploaded through ``upload_zip_to_report_store``.
