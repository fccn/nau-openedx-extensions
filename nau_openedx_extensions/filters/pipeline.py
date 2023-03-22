"""
Defined filters.
"""

from fnmatch import fnmatch

from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.edxapp_wrapper.course_module import get_course_name, get_other_course_settings


class FilterEnrollmentByDomain(PipelineStep):   # pylint: disable=too-few-public-methods
    """
    Stop enrollment process raising PreventEnrollment exception if the user has an email
    with a domain that is not in those allowed by a course in DomainsAllowedPerCourse.
    Example usage:
    Add the following configurations to your configuration file:
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.course.enrollment.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.filters.pipeline.FilterEnrollmentByDomain"
                ]
            }
        }
    """

    def run_filter(self, user, course_key, mode):   # pylint: disable=unused-argument, arguments-differ
        """Filter."""

        user_domain = user.email.split("@")[1].lower()
        other_course_settings = get_other_course_settings(course_key)
        domains_allowed = other_course_settings.get("value", {}).get("filter_enrollment_by_domain_list", [])
        allowed = False
        for domain in domains_allowed:
            if user_domain == domain or fnmatch(user_domain, f"*.{domain}"):
                allowed = True
                break
        if domains_allowed and not allowed:
            custom_message = other_course_settings.get("value", {}).get(
                "filter_enrollment_by_domain_custom_exception_message",
                _("If you think this is an error, contact the course support."))
            exception_msg = _("You can't enroll on this course because your email domain is not allowed. "
                              "%(custom_message)s") % {
                'custom_message': custom_message}
            raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)
        return {}


class FilterEnrollmentRequireUserActive(PipelineStep):   # pylint: disable=too-few-public-methods
    """
    Stop enrollment process raising PreventEnrollment exception if the course requires that the
    user should be active before creating the enrollment.
    Example usage:
    Add the following configurations to your configuration file:
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.course.enrollment.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.filters.pipeline.FilterEnrollmentRequireUserActive"
                ]
            }
        }
    """

    def run_filter(self, user, course_key, mode):   # pylint: disable=unused-argument, arguments-differ
        """Filter."""
        other_course_settings = get_other_course_settings(course_key)
        require_user_active = other_course_settings.get("value", {}).get("filter_enrollment_require_user_active", False)
        if require_user_active and not user.is_active:
            course_name = get_course_name(course_key)
            exception_msg = _("You need to activate your account before you can enroll the course "
                              "{course_name}.").format(course_name=course_name)
            raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)
        return {}
