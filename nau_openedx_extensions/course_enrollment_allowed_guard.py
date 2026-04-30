"""
Prevent incompatible CourseEnrollmentAllowed rows when a course requires NIF.

Instructor invites (Course enrollment allowed) trigger auto-enrollment on user
activation; FilterEnrollmentRequireNIF blocks that enrollment if the learner
has no NIF, leaving the platform in a broken state. Blocking CEA creation
avoids that.
"""

from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.utils.translation import gettext as _

from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings


def enforce_no_course_enrollment_allowed_when_nif_required(course_id):
    """
    Raise ValidationError if the course has filter_enrollment_require_nif enabled.

    Args:
        course_id: CourseKey or course id accepted by modulestore.
    """
    if course_id is None:
        return
    other_course_settings = get_other_course_settings(course_id)
    filter_by_nif = other_course_settings.get("value", {}).get("filter_enrollment_require_nif")
    if filter_by_nif:
        raise ValidationError(
            _(
                "This course requires a NIF (or Autenticação Gov) on learner accounts. "
                "You cannot add an email to Course enrollment allowed for this course. "
                "Disable the NIF requirement in the course other settings or ask learners "
                "to self-enroll after they complete NIF verification."
            )
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
