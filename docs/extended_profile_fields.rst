Extended profile fields
=======================

NAU collects characterization data that Open edX does not model natively. Those
fields live on ``NauUserExtendedModel``, which hangs off the user account, so
they are collected once per learner rather than per course.

This page documents the field mapping, where each value comes from, how it is
validated, and what has to be configured for the fields to be visible.

Fields
------

.. list-table::
   :header-rows: 1
   :widths: 22 14 20 44

   * - Field
     - Type
     - Source
     - Notes
   * - ``nif``
     - text
     - registration, account
     - Portuguese taxpayer number. Validated by ``NifValidator``, which runs the
       checksum in ``nau_openedx_extensions.utils.nif``. The ``nau_nif`` property
       on ``User`` falls back to the citizen card NIF (``cc_nif``) when the field
       itself is empty.
   * - ``employment_situation``
     - choice
     - registration, account
     - 15 options plus one legacy value, see `Employment situation`_.
   * - ``nuts``
     - choice
     - registration, account
     - "NUTS II - NUTS III" as a single merged field, 27 options.
   * - ``cae4``
     - choice
     - registration, account
     - Economic activity sector, 24 options.

The native profile fields Phase 1 also relies on (sex, year of birth, country of
residence, education level) are ``gender``, ``year_of_birth``, ``country`` and
``level_of_education`` on the platform's own ``UserProfile``. They are not
duplicated here.

All four fields are ``blank=True, null=True``. That is deliberate: a learner has
to be able to save a partial profile, and which fields are mandatory is a
separate, configurable decision (see `Requiring fields for course access`_).

Values and labels
-----------------

The controlled lists live in
``nau_openedx_extensions.custom_registration_form.choices``. Each entry is a
short stable code stored in the database, paired with a Portuguese label shown
to the user:

.. code-block:: python

    ("public_senior_technician", "Trabalhador da Função Pública: Técnico/a Superior")

Two consequences worth knowing:

* Rewording a label is a code change, not a data migration, because the stored
  value never changes.
* The labels are **not** wrapped in ``gettext``. They are exported in
  ``student_profile_info``, which runs inside a Celery task where the active
  language is not guaranteed, and the reports have to read in Portuguese. If
  another language is ever needed, wrap the labels and add the catalogs.

Reports receive the label, not the code, because the ``User`` properties call
``get_FOO_display()``:

.. code-block:: text

    nau_nif
    nau_user_extended_model_cc_nic
    nau_user_extended_model_employment_situation
    nau_user_extended_model_nuts
    nau_user_extended_model_cae4

Add these to ``student_profile_download_fields`` and
``additional_student_profile_attributes`` in site configuration for them to
appear in ``student_profile_info``.

Employment situation
--------------------

The option list was replaced: the previous "Contrato com instituição pública"
was split upstream into ten "Função Pública" entries. Existing rows stored the
English display strings and are remapped in place by migration
``0015_extended_profile_fields``.

"Public service contract" has no single target among the ten new entries, so it
keeps its own code (``public_service_contract``) and stays selectable, labelled
as the previous option. This is not cosmetic: ``partial_update`` calls
``full_clean()`` on the whole model whenever any account field is saved, so
dropping that value from ``choices`` would break account edits for every learner
still holding it, on a field they did not touch.

Validation
----------

There is no bespoke validation layer. Validation comes from three places:

* **Choices.** ``nuts``, ``cae4`` and ``employment_situation`` are validated
  against their lists by Django whenever ``full_clean()`` runs, which the account
  update path does on every save.
* **NIF.** ``NifValidator`` runs the checksum, so a syntactically well formed but
  invalid number is rejected.
* **The gate.** For course access, a value that is present but invalid does not
  count as filled, see below.

Requiring fields for course access
----------------------------------

Whether a field blocks course access is set per course in the advanced settings,
the same way ``filter_enrollment_require_nif`` already works:

.. code-block:: json

    {
        "filter_enrollment_require_profile_fields": ["nif", "nuts", "cae4"]
    }

A course without the setting does not gate on anything.

Names are resolved against ``NauUserExtendedModel`` first and then the native
``UserProfile``, so ``nuts`` and ``year_of_birth`` both work. ``nif`` is checked
with ``is_nif_valid`` rather than for mere presence.

A name that matches neither model is logged and skipped rather than treated as
missing, because blocking a whole course over a typo in the advanced settings is
a worse failure than ignoring the entry.

Three filters read this setting, covering the three ways into a course:

.. list-table::
   :header-rows: 1
   :widths: 38 62

   * - Filter
     - Where it acts
   * - ``FilterEnrollmentRequireProfileFields``
     - The enrollment itself. The API answers 403 with the message naming the
       missing fields.
   * - ``RequireProfileFieldsOnCourseAbout``
     - The course about page, replaced by the completion panel.
   * - ``RequireProfileFieldsOnXBlockRender``
     - The course content. This is the one that matters for a learner who is
       already enrolled, from before the course required the fields or through a
       bulk enrollment. Staff are let through.

All three are registered in ``OPEN_EDX_FILTERS_CONFIG``; see their docstrings in
``nau_openedx_extensions.filters.pipeline`` for the exact pipeline entries.

What the gate does not cover
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The course outline, which the learning MFE builds from
``/api/course_home/outline/``, is not gated. ``lms/djangoapps/course_home_api``
exposes no ``openedx_filters`` hook, so there is nowhere to attach one. A learner
missing the fields sees the section titles but cannot open any content.

Also note that ``RequireProfileFieldsOnCourseAbout`` never runs when
``ENABLE_MKTG_SITE`` is on, which is how NAU runs. The course about view
redirects to the course home before the filter is reached:

.. code-block:: python

    if _course_home_redirect_enabled():
        return redirect(course_home_url(course_key))

The filter is kept because it is the right gate for deployments without a
marketing site, but the content filter is what does the work at NAU.

Configuration required for the fields to be visible
---------------------------------------------------

The model alone is not enough. Without this configuration the fields exist in
the database and are never shown:

``REGISTRATION_EXTENSION_FORM``
    Must point at ``nau_openedx_extensions.custom_registration_form.forms.NauUserExtendedForm``.
    It is read from Django settings only, never from site configuration.

``extended_profile_fields`` (site configuration)
    Must list every field name. This is a strict allowlist:
    ``RegistrationFieldsContext._field_can_be_saved()`` drops anything missing
    from it, silently and with no error. It is also what the account page's
    extended fields component filters against.

``REGISTRATION_EXTRA_FIELDS`` and ``REGISTRATION_FIELD_ORDER``
    Control whether a field is asked for at registration and in what order. Note
    that ``nif`` currently ships as ``hidden``.

``NAU_ACCOUNTS_CC_VISIBLE_FIELDS``
    Which of the extended fields the account page exposes. It already includes
    the four.

A field marked ``optional`` renders on the progressive profiling page, which the
learner can skip, and that page saves through the account API into
``UserProfile.meta`` rather than into ``NauUserExtendedModel``. Fields that must
land in this model have to be collected at registration itself.

Known limitations
-----------------

* Editing these fields on the account page depends on extension points that
  exist in the ``fccn/openedx-platform`` fork, not in upstream Open edX. Upstream
  added ``ExtendedProfileFieldsSlot`` to ``frontend-app-account`` for this, but it
  landed after the Teak cut and is available from Ulmo onwards.
* The completion panel links to the account page with the missing field names in
  a ``missing`` query parameter. The account page does not read it yet, so
  nothing is highlighted there; that needs a change in the frontend component
  that renders the extended profile.
* The enrollment API returns the reason in the 403 body, as ``message`` and
  ``localizedMessage``, but neither ``frontend-app-learning`` nor
  ``frontend-app-learner-dashboard`` reads it, so a learner clicking enroll from
  an MFE sees no explanation. Showing it needs a frontend change.
* The completion panel carries no colours of its own. It uses ``btn btn-primary``
  and ``btn btn-secondary`` so the site theme paints it.
