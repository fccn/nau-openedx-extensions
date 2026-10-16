Setting up the NAU profile fields
=================================

How to turn the extended profile fields on, what to configure, and how to make
a course require them.

This page is the how-to. For what each field means, where its value comes from
and why the design is the way it is, see `extended_profile_fields.rst
<extended_profile_fields.rst>`_.

What you get
------------

* Four extra fields asked for at registration: NIF, employment situation, NUTS
  and CAE4.
* A learner can correct them afterwards on their account page.
* Any course can refuse access until the fields it cares about are filled in,
  including courses the learner is already enrolled in.
* The values are exported in ``student_profile_info``.

Three pieces have to be in place
--------------------------------

None of them works alone. If the fields are collected but not editable, or
gated but not collected, one of these is missing.

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Piece
     - Where
     - What breaks without it
   * - Platform hooks
     - ``fccn/openedx-platform``
     - The account page neither shows nor saves the fields. Registration still
       works, so a blocked learner has no way to unblock themselves.
   * - The plugin
     - ``nau-openedx-extensions``
     - Nothing exists: no fields, no gate.
   * - Configuration
     - ``nau-tutor-configs``
     - The fields exist in the database and are never shown to anyone.

Step 1: the platform hooks
--------------------------

The account page reaches the plugin through three ``run_extension_point`` calls
in ``openedx/core/djangoapps/user_api/accounts/``. They live in the NAU fork
only, restored in `openedx-platform#48
<https://github.com/fccn/openedx-platform/pull/48>`_.

Check the image you are deploying actually has them:

.. code-block:: bash

    grep -rn "run_extension_point" \
        openedx/core/djangoapps/user_api/accounts/

Six lines is correct, an import and a call in each of ``api.py``,
``serializers.py`` and ``settings_views.py``. Zero means you are on an image
built before #48, and steps 4 and 5 will appear to work while the account page
stays empty.

Step 2: install the plugin and migrate
--------------------------------------

The fields are a real model, not a JSON blob, so they need a migration:

.. code-block:: bash

    ./manage.py lms migrate nau_openedx_extensions

Migration ``0015`` also rewrites existing ``employment_situation`` values,
which used to be stored as English display strings, into the new codes. It is
reversible.

Step 3: Django settings
-----------------------

``REGISTRATION_EXTENSION_FORM`` is read from Django settings only, never from
site configuration:

.. code-block:: python

    REGISTRATION_EXTENSION_FORM = (
        "nau_openedx_extensions.custom_registration_form.forms.NauUserExtendedForm"
    )

Step 4: site configuration
--------------------------

Four keys, and two of them have to agree with each other.

``extended_profile_fields``
    The list the registration and account pages filter against. A field missing
    from it is dropped silently, with no error anywhere.

``NAU_ACCOUNTS_CC_VISIBLE_FIELDS``
    Which fields the account page shows and accepts. Defaults to
    ``["employment_situation", "nif", "allow_newsletter", "nuts", "cae4"]`` if
    you do not set it.

    **These two lists have to contain the same NAU fields.** A field in only one
    of them renders on the page and then silently fails to save, which is the
    single most common way to get this wrong.

``REGISTRATION_EXTRA_FIELDS``
    Whether each field is ``required``, ``optional`` or ``hidden`` at
    registration.

``REGISTRATION_FIELD_ORDER``
    The order they appear in.

A working set:

.. code-block:: json

    {
        "extended_profile_fields": [
            "nif", "employment_situation", "nuts", "cae4", "allow_newsletter"
        ],
        "NAU_ACCOUNTS_CC_VISIBLE_FIELDS": [
            "employment_situation", "nif", "allow_newsletter", "nuts", "cae4"
        ],
        "REGISTRATION_EXTRA_FIELDS": {
            "nif": "optional",
            "employment_situation": "optional",
            "nuts": "optional",
            "cae4": "optional"
        }
    }

Leave the four fields ``optional`` unless you want to turn away every new
registration that cannot supply them. Which fields are genuinely mandatory is a
per-course decision, made in step 6, not a platform-wide one.

Step 5: register the filters
----------------------------

Three filters, one per way into a course. Registering only some of them leaves
a gap:

.. code-block:: python

    OPEN_EDX_FILTERS_CONFIG = {
        "org.openedx.learning.course.enrollment.started.v1": {
            "fail_silently": False,
            "pipeline": [
                "nau_openedx_extensions.filters.pipeline.FilterEnrollmentRequireProfileFields",
            ],
        },
        "org.openedx.learning.course_about.render.started.v1": {
            "fail_silently": False,
            "pipeline": [
                "nau_openedx_extensions.filters.pipeline.RequireProfileFieldsOnCourseAbout",
            ],
        },
        "org.openedx.learning.xblock.render.started.v1": {
            "fail_silently": False,
            "pipeline": [
                "nau_openedx_extensions.filters.pipeline.RequireProfileFieldsOnXBlockRender",
            ],
        },
    }

At NAU this is done by ``append_filter_config()`` in
``nau-tutor-configs/plugins/platform_config.py``, which adds to the pipelines
rather than replacing them, so other NAU filters keep working.

The xblock one is the one that matters most. ``ENABLE_MKTG_SITE`` redirects the
course about page before its filter ever runs, and the enrollment filter only
covers new enrollments, so for anyone already enrolled the content filter is
the only thing standing between them and the course.

Step 6: check it works
----------------------

.. code-block:: bash

    ./manage.py lms shell

.. code-block:: python

    from django.contrib.auth import get_user_model
    from django.test import RequestFactory
    from openedx.core.djangoapps.user_api.accounts.api import get_account_settings

    user = get_user_model().objects.get(username="someone")
    request = RequestFactory().get("/")
    request.user = user

    data = get_account_settings(request, [user.username])[0]
    print(sorted(f["field_name"] for f in data["extended_profile"]))

You should see the fields from ``NAU_ACCOUNTS_CC_VISIBLE_FIELDS``, each once.
An empty list means step 1 or step 4 is wrong. A field appearing twice means
you are on a plugin version from before the merge fix.

Requiring fields in a course
----------------------------

Per course, in Studio: **Settings > Advanced Settings > Other Course Settings**.

.. code-block:: json

    {
        "filter_enrollment_require_profile_fields": ["nif", "nuts", "cae4"]
    }

A course without the key gates on nothing, which is the default. Every course
starts ungated and stays that way until someone adds this.

Which names are valid
~~~~~~~~~~~~~~~~~~~~~

Eight, covering everything ARTE asks for. Four come from the NAU model and four
from the platform's own profile, and you write them the same way:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Name
     - Lives on
     - Note
   * - ``nif``
     - NAU model
     - Checked with the checksum, not just for presence. An invalid NIF counts
       as not filled.
   * - ``employment_situation``
     - NAU model
     -
   * - ``nuts``
     - NAU model
     -
   * - ``cae4``
     - NAU model
     -
   * - ``gender``
     - ``UserProfile``
     -
   * - ``year_of_birth``
     - ``UserProfile``
     -
   * - ``country``
     - ``UserProfile``
     - Country of residence.
   * - ``level_of_education``
     - ``UserProfile``
     -

A name that is neither is logged and ignored, not treated as missing. A typo in
this setting will not lock the course for everyone, it will quietly gate on
less than you intended, so check the LMS log after editing it.

What the learner runs into
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - They try to
     - What happens
   * - Enrol
     - Refused with 403. The body names the missing fields in ``message`` and
       ``localizedMessage``.
   * - Open the course about page
     - Replaced by the completion panel, which links to the account page.
   * - Open course content, already enrolled
     - Same panel instead of the unit. Staff are let through.

Inviting people by email
~~~~~~~~~~~~~~~~~~~~~~~~

A Course Enrollment Allowed row is refused for a course that requires these
fields. Without that, an invited learner would be enrolled automatically on
activation and land enrolled but locked out, with nothing explaining why.

Reports
-------

Add the properties to site configuration to get the values into
``student_profile_info``:

.. code-block:: json

    {
        "student_profile_download_fields": [
            "nau_nif",
            "nau_user_extended_model_cc_nic",
            "nau_user_extended_model_employment_situation",
            "nau_user_extended_model_nuts",
            "nau_user_extended_model_cae4"
        ],
        "additional_student_profile_attributes": [
            "nau_nif",
            "nau_user_extended_model_employment_situation",
            "nau_user_extended_model_nuts",
            "nau_user_extended_model_cae4"
        ]
    }

The CSV carries the Portuguese label, not the stored code, so
``employment_situation`` reads ``Estudante`` and not ``student``. If that column
was already in your reports it changes value the day this ships, without any
configuration change on your side.

When it does not work
---------------------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Symptom
     - Cause
   * - The fields are not on the account page at all
     - Either the image predates openedx-platform#48 (step 1), or
       ``extended_profile_fields`` does not list them (step 4).
   * - A field shows but saving does nothing
     - It is in ``extended_profile_fields`` and not in
       ``NAU_ACCOUNTS_CC_VISIBLE_FIELDS``. The page renders it and the plugin
       refuses to write it. Check the LMS log for "Ignoring extended profile
       field".
   * - A value the learner entered before is now blank
     - Expected once. It only ever reached ``UserProfile.meta``, and the page
       now shows the model, which is what gates the course. They have to enter
       it again.
   * - The gate lets someone in who has not filled the fields
     - The name in the course setting does not match any field, so it is being
       ignored. Check spelling against the table above and the LMS log.
   * - The gate blocks someone who has filled everything
     - For ``nif``, the stored number fails its checksum, which counts as not
       filled.
   * - Enrolment is blocked but the course content still opens
     - ``RequireProfileFieldsOnXBlockRender`` is not registered (step 5).

What this does not do
---------------------

* **The course outline still renders.** A gated learner sees section and unit
  titles and cannot open any of them. ``course_home_api`` exposes no filter
  hook, so there is nowhere to attach one.
* **MFE enrolment buttons show no reason.** The 403 carries the explanation,
  but ``frontend-app-learning`` and ``frontend-app-learner-dashboard`` do not
  read it. Richie does.
* **Nothing is backfilled.** Learners who registered before these fields have
  no values and no row, and the gate correctly treats them as not filled. They
  fill them the first time a course asks.
