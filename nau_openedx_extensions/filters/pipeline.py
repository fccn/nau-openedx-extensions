"""
Defined filters.
"""

from fnmatch import fnmatch

from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings


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

    def run_filter(self, user, course_key, mode):   # pylint: disable=unused-argument, no-self-use
        """Filter."""

        user_domain = user.email.split("@")[1]
        other_course_settings = get_other_course_settings(course_key)
        domains_allowed = other_course_settings.get("value", {}).get("filter_enrollment_by_domain_list", [])
        allowed = False
        for domain in domains_allowed:
            if fnmatch(user_domain, f"*{domain}"):
                allowed = True
                break
        if domains_allowed and not allowed:
            raise CourseEnrollmentStarted.PreventEnrollment(_("You can't enroll on this course because your email\
                 domain is not allowed. If you think this is an error, contact the course support"))
        return {}