"""
File that contains the definition of all signals and its receivers for LMS.
"""

from nau_openedx_extensions.common.signals import fix_course_overview_required_fields  # pylint: disable=unused-import
from nau_openedx_extensions.verify_student.id_verification import (  # pylint: disable=unused-import
    event_receiver_no_id_verify_for_enrollment_modes,
)
