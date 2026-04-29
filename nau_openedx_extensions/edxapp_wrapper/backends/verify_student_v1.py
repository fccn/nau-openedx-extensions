"""
Real implementation of user id verifications service.
"""
import logging

from django.contrib.auth import get_user_model
from lms.djangoapps.verify_student.models import ManualVerification  # pylint: disable=import-error
from lms.djangoapps.verify_student.signals.signals import (  # pylint: disable=import-error
    emit_idv_attempt_approved_event,
)

log = logging.getLogger(__name__)


def get_user_id_verifications(user_id, *args, **kwargs):
    """
    Read the user's `ManualVerification` from the edx-platform.

    Args:
        user: The user id to read the Id Verifications.

    Returns:
        An enumeration of those Id Verifications
    """
    user = get_user_model().objects.get(id=user_id)
    return ManualVerification.objects.filter(user=user).order_by('-created_at')


def create_user_id_verification(user_id, *args, **kwargs):
    """
    Create a new `ManualVerification` on the edx-platform and emit the IDV_ATTEMPT_APPROVED
    event so that Teak's certificate generation pipeline is triggered.

    Args:
        user: The user id that this Id verification should be created.

    Returns:
        The object created
    """
    user = get_user_model().objects.get(id=user_id)
    try:
        name = user.profile.name
    except Exception:  # pylint: disable=broad-except
        name = user.get_full_name() or user.username
    verification = ManualVerification(user=user, name=name, *args, **kwargs)
    verification.save()

    # Emit IDV_ATTEMPT_APPROVED so Teak's certificate generation pipeline is triggered.
    # In Teak, the certificates app listens to this event (IDV_ATTEMPT_APPROVED) to regenerate
    # certificates after a user is ID-verified. Without this, the ManualVerification is created
    # but the certificate pipeline is never notified and certificates remain blocked.
    try:
        emit_idv_attempt_approved_event(
            attempt_id=verification.id,
            user=user,
            status=kwargs.get('status', 'approved'),
            name=user.profile.name,
            expiration_date=kwargs.get('expiration_date'),
        )
    except Exception:  # pylint: disable=broad-except
        log.exception(
            "Failed to emit IDV_ATTEMPT_APPROVED event for user %d (ManualVerification id=%d). "
            "The ManualVerification was saved and user_is_verified() will still return True, "
            "but certificate regeneration may not be triggered automatically.",
            user_id,
            verification.id,
        )

    return verification
