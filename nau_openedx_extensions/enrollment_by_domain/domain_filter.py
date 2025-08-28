"""
Enrollment domain filter implementation.
"""

import logging
from fnmatch import fnmatch

from django.conf import settings
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.edxapp_wrapper import site_configuration_helpers as configuration_helpers
from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings
from nau_openedx_extensions.edxapp_wrapper.student import get_enrollment, get_student_course_enrollment_allowed
from nau_openedx_extensions.enrollment_by_domain.models import EnrollmentAllowedList

logger = logging.getLogger(__name__)


class FilterEnrollmentByAllowedList(PipelineStep):
    """
    Stop enrollment process raising PreventEnrollment exception if the user has an email
    with a domain that is not in those allowed by an EnrollmentAllowedList referenced
    by the course setting.

    This filter fetches allowed domains from the EnrollmentAllowedList model, referenced
    via a new course advanced setting field 'filter_enrollment_allowed_list_code'. It
    validates domain, user account status, and uses custom error messages.

    It preserves compatibility with instructor-allowed enrollments (CourseEnrollmentAllowed).
    The user can enroll even if their email domain doesn't match the allowed list if the instructor
    has manually added their email as a Course Enrollment Allowed.

    A race condition can raise an error if the user account already exists and is inactive,
    in this case the instructor couldn't add manually the custom user to the course.
    If this happens, the user needs to activate their account before the instructor
    could create the enrollment.

    To activate it, the course needs to have the setting 'filter_enrollment_allowed_list_code'
    set to the code of an EnrollmentAllowedList inside the course advanced settings.

    Example usage:
    Add the following configurations to your configuration file:
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.course.enrollment.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.enrollment_by_domain.domain_filter.FilterEnrollmentByAllowedList"
                ]
            }
        }

    Course Advanced Settings Example:
        {
            "filter_enrollment_allowed_list_code": "university-partners"
        }

    Optional course-level custom message:
        {
            "filter_enrollment_allowed_list_code": "university-partners",
            "filter_enrollment_by_domain_custom_exception_message": "Custom error message"
        }
    """

    def run_filter(self, user, course_key, mode):   # pylint: disable=unused-argument, arguments-differ
        """
        Execute the enrollment filter.

        Args:
            user: User object attempting to enroll
            course_key: CourseKey of the course
            mode: Enrollment mode (audit, verified, etc.)

        Returns:
            dict: Empty dict if enrollment should proceed

        Raises:
            CourseEnrollmentStarted.PreventEnrollment: If enrollment should be blocked
        """
        other_course_settings = get_other_course_settings(course_key)
        course_settings = other_course_settings.get("value", {})
        allowed_list_code = (
            course_settings.get("filterEnrollmentAllowedListCode") or
            course_settings.get("filter_enrollment_allowed_list_code")
        )
        if not allowed_list_code:
            # No filter configured, allow enrollment
            return {}

        # Check user account status first
        if not user.is_active:
            platform_name = configuration_helpers.get_value("platform_name", settings.PLATFORM_NAME)
            exception_msg = _(
                "You need to activate your account before you can enroll in the course. "
                "Check your {email} inbox for an account activation link from {platform_name}."
            ).format(email=user.email, platform_name=platform_name)

            logger.info(
                "Blocked enrollment for inactive user %s in course %s",
                user.username, course_key
            )
            raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)

        # Check if instructor has manually allowed this user
        cea = get_student_course_enrollment_allowed(user, course_key)
        if cea:
            logger.debug(
                "User %s is manually allowed by instructor in course %s, skipping domain check",
                user.username, course_key
            )
            return {}

        # Skip domain checking if user is already enrolled
        if get_enrollment(user, course_key):
            logger.debug(
                "User %s is already enrolled in course %s, skipping domain check",
                user.username, course_key
            )
            return {}

        # Check domain restrictions
        try:
            allowed_list = EnrollmentAllowedList.objects.get(code=allowed_list_code)

            if not self._is_user_email_allowed(user, allowed_list):
                # Get the complete error message (custom or default)
                exception_msg = self._get_error_message(allowed_list, other_course_settings)

                logger.info(
                    "Blocked enrollment for user %s (%s) in course %s - domain not in allowed list %s",
                    user.username, user.email, course_key, allowed_list_code
                )

                raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)

            logger.debug(
                "User %s (%s) allowed to enroll in course %s - domain matches allowed list %s",
                user.username, user.email, course_key, allowed_list_code
            )

        except EnrollmentAllowedList.DoesNotExist:
            # Log the error but don't block enrollment if list doesn't exist
            logger.error(
                "EnrollmentAllowedList with code '%s' not found for course '%s'. "
                "Enrollment filter will be skipped. Please check course configuration.",
                allowed_list_code, course_key
            )

        return {}

    def _is_user_email_allowed(self, user, allowed_list):
        """
        Check if the user email domain is in the allowed list.

        Supports exact domain matching and subdomain matching using fnmatch.
        For example, if 'university.edu' is in the allowed list:
        - 'student@university.edu' -> allowed (exact match)
        - 'faculty@cs.university.edu' -> allowed (subdomain match)
        - 'user@other-university.edu' -> not allowed

        Args:
            user: The user trying to enroll
            allowed_list: EnrollmentAllowedList instance

        Returns:
            bool: True if user's domain is allowed, False otherwise
        """
        if not user.email or '@' not in user.email:
            logger.warning("User %s has invalid email format: %s", user.username, user.email)
            return False

        user_domain = user.email.split("@")[1].lower()

        # Get all domains from the allowed list (using select_related would be overkill here)
        allowed_domains = allowed_list.domains.values_list('domain', flat=True)

        for domain in allowed_domains:
            domain = domain.lower().strip()

            # Check exact match first (more efficient)
            if user_domain == domain:
                logger.debug("Exact domain match: %s == %s", user_domain, domain)
                return True

            # Check subdomain match using fnmatch
            if fnmatch(user_domain, f"*.{domain}"):
                logger.debug("Subdomain match: %s matches *.%s", user_domain, domain)
                return True

        logger.debug(
            "Domain %s not found in allowed domains: %s",
            user_domain, list(allowed_domains)
        )
        return False

    def _get_error_message(self, allowed_list, other_course_settings):
        """
        Get the appropriate error message with priority order.

        Priority:
        1. Course-level custom message (from advanced settings)
        2. List-level custom message (from EnrollmentAllowedList model)
        3. Default message

        Args:
            allowed_list: EnrollmentAllowedList instance
            other_course_settings: Course advanced settings

        Returns:
            str: The complete error message to use
        """
        course_settings = other_course_settings.get("value", {})

        # Priority 1: Course-level custom message (check both formats)
        course_custom_message = (
            course_settings.get("filterEnrollmentByDomainCustomExceptionMessage") or  # camelCase
            course_settings.get("filter_enrollment_by_domain_custom_exception_message")  # snake_case
        )

        if course_custom_message and course_custom_message.strip():
            logger.debug("Using course-level custom error message")
            return course_custom_message.strip()

        # Priority 2: List-level custom message
        if allowed_list.custom_exception_message and allowed_list.custom_exception_message.strip():
            logger.debug("Using list-level custom error message")
            return allowed_list.custom_exception_message.strip()

        # Priority 3: Default complete message
        logger.debug("Using default error message")
        return _(
            "You can't enroll on this course because your email domain is not allowed. "
            "If you think this is an error, contact the course support."
        )

    def __str__(self):
        """String representation for debugging."""
        return f"{self.__class__.__name__}"

    def __repr__(self):
        """Developer representation for debugging."""
        return f"<{self.__class__.__name__}>"
