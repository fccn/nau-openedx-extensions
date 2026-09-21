"""
Prevent incompatible CourseEnrollmentAllowed rows when a course requires
profile data.

Instructor invites (Course enrollment allowed) trigger auto-enrollment on user
activation, and the enrollment filters block that enrollment if the learner is
missing what the course asks for, leaving the platform in a broken state.
Blocking CEA creation avoids that.
"""

from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.utils.translation import gettext as _

from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings


def enforce_no_course_enrollment_allowed_when_nif_required(course_id):
    """
    Raise ValidationError if the course requires profile data on learner accounts.

    Covers both filter_enrollment_require_nif and the Phase 1
    filter_enrollment_require_profile_fields. The name is kept for backwards
    compatibility, it is imported elsewhere.

    Args:
        course_id: CourseKey or course id accepted by modulestore.
    """
    if course_id is None:
        return
    other_course_settings = get_other_course_settings(course_id).get("value", {})

    if other_course_settings.get("filter_enrollment_require_nif"):
        raise ValidationError(
            _(
                "This course requires a NIF (or Autenticação Gov) on learner accounts. "
                "You cannot add an email to «Course enrollment allowed» for this course. "
                "Disable the NIF requirement at:\n"
                "Studio course page -> Settings -> Advanced Settings -> Other course settings\n"
                "Or ask learners to self-enroll after they complete NIF verification."
            )
        )

    required_fields = other_course_settings.get("filter_enrollment_require_profile_fields")
    if required_fields:
        raise ValidationError(
            _(
                "This course requires learners to have {fields} on their account. "
                "You cannot add an email to «Course enrollment allowed» for this course, "
                "because the invite would auto-enrol someone who is then kept out of the "
                "content.\n"
                "Change the requirement at:\n"
                "Studio course page -> Settings -> Advanced Settings -> Other course settings\n"
                "Or ask learners to self-enroll once their profile is complete."
            ).format(fields=", ".join(required_fields))
        )


def _course_enrollment_allowed_pre_save(sender, instance, raw, **kwargs):  # pylint: disable=unused-argument
    if raw:
        return
    enforce_no_course_enrollment_allowed_when_nif_required(instance.course_id)


def connect_course_enrollment_allowed_nif_guard():
    """Attach pre_save guard to edx-platform CourseEnrollmentAllowed (no-op in test stubs)."""
    from nau_openedx_extensions.edxapp_wrapper.student import (  # pylint: disable=import-outside-toplevel
        get_course_enrollment_allowed_model,
    )

    cea_model = get_course_enrollment_allowed_model()
    if cea_model is None:
        return
    pre_save.connect(
        _course_enrollment_allowed_pre_save,
        sender=cea_model,
        dispatch_uid="nau_openedx_extensions.course_enrollment_allowed_nif_guard",
    )
