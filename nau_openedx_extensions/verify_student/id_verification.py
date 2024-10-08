"""
NAU Custom code to skip Open edX ID Verification module.
"""
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.dispatch import receiver
from openedx_events.learning.data import CourseEnrollmentData
from openedx_events.learning.signals import COURSE_ENROLLMENT_CHANGED
from pytz import UTC

from nau_openedx_extensions.edxapp_wrapper.verify_student import create_user_id_verification, get_user_id_verifications

log = logging.getLogger(__name__)


@receiver(COURSE_ENROLLMENT_CHANGED)
def event_receiver_no_id_verify_for_enrollment_modes(enrollment: CourseEnrollmentData, **kwargs):
    """
    This receiver will ignore / skip the id verification of the Open edX platform.
    Meaning that will create `ManualVerification` object if `enrollment_mode` is defined in the
    `NAU_NO_ID_VERIFY_FOR_ENROLLMENT_MODES` setting, defaults to just the `verified` enrollment mode.
    It should be configured using the Open edX signal:
    `openedx_events.learning.signals.COURSE_ENROLLMENT_CHANGED`
    """
    log.info("On event receiver that makes removes the need of ID Verify for some enrollment modes")
    enrollment_mode = enrollment.mode
    enrollment_modes_to_skip_as_str = getattr(settings, 'NAU_NO_ID_VERIFY_FOR_ENROLLMENT_MODES', 'verified')
    enrollment_modes_to_skip = list(map(str.strip, enrollment_modes_to_skip_as_str.split(',')))
    if enrollment_mode in enrollment_modes_to_skip:
        user_id = enrollment.user.id
        now = datetime.now(UTC)

        def verification_active_predicate(verification):
            return verification.active_at_datetime(now)

        user_manual_verifications = get_user_id_verifications(user_id)
        verification_active = next(filter(verification_active_predicate, user_manual_verifications), None)
        if verification_active:
            log.info("User %d already has an ID verification", user_id)
        else:
            expiration_date = now + timedelta(days=36500)  # 100 years
            log.info("Create user ID Verification for %d", user_id)
            create_user_id_verification(
                user_id,
                status='approved',
                expiration_date=expiration_date,
                reason="Skip id verification from nau_openedx_extensions"
            )
