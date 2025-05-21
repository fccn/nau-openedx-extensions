"""
Defined filters.
"""

from fnmatch import fnmatch

from django.urls import reverse

from django.conf import settings
from django.db.models.query import QuerySet
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.edxapp_wrapper import site_configuration_helpers as configuration_helpers
from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings
from nau_openedx_extensions.edxapp_wrapper.student import get_enrollment, get_student_course_enrollment_allowed

from web_fragments.fragment import Fragment
from django.template import Context, Template
import pkg_resources
from crum import get_current_request
import logging

TEMPLATE_ABSOLUTE_PATH = "/instructor_dashboard/"
BLOCK_CATEGORY = "certificate_export"


class FilterEnrollmentByDomain(PipelineStep):   # pylint: disable=too-few-public-methods
    """
    Stop enrollment process raising PreventEnrollment exception if the user has an email
    with a domain that is not in those allowed by a course in DomainsAllowedPerCourse.

    It also allows instructor to override the filter. The user can enroll even if its email
    domain doesn't be one of the allowed if the instructor has added its email as one of the
    Course Enrolment Allowed. A race condition can raise an error, if the user account already
    exist and is inactive, in this case the instructor couldn't add manualy the custom user to
    the course. If this happens, the user needs to activate their account before the instructor
    could create the enrollment.

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

        other_course_settings = get_other_course_settings(course_key)
        domains_allowed = (
            other_course_settings.get("value", {}).get("filter_enrollment_by_domain_list") or
            other_course_settings.get("value", {}).get("filterEnrollmentByDomainList")
        )

        if domains_allowed:
            if not user.is_active:
                platform_name = configuration_helpers.get_value("platform_name", settings.PLATFORM_NAME)
                exception_msg = _(
                    "You need to activate your account before you can enroll in the course. "
                    "Check your {email} inbox for an account activation link from {platform_name}."
                ).format(email=user.email, platform_name=platform_name)
                raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)

            cea = get_student_course_enrollment_allowed(user, course_key)
            # if the student is allowed to enroll, skip checking the email domain
            # validate the email domain if user is not already enrolled
            if not cea and not get_enrollment(user, course_key):
                if not FilterEnrollmentByDomain._is_user_email_allowed(user, domains_allowed):
                    custom_message = other_course_settings.get("value", {}).get(
                        "filter_enrollment_by_domain_custom_exception_message",
                        _("If you think this is an error, contact the course support."))
                    exception_msg = _("You can't enroll on this course because your email domain is not allowed. "
                                      "%(custom_message)s") % {
                        'custom_message': custom_message}
                    raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)

        return {}

    @staticmethod
    def _is_user_email_allowed(user, domains_allowed):
        """
        Check if the user email is a domain or sub-domain of the allowed domains.
        """
        user_domain = user.email.split("@")[1].lower()
        for domain in domains_allowed:
            if user_domain == domain or fnmatch(user_domain, f"*.{domain}"):
                return True
        return False


class FilterUsersWithAllowedNewsletter(PipelineStep):
    """
    Filter the Schedules QuerySet to only keep those whose associated user has
    the `allow_newsletter` field set to `True`. If the user does not have the
    `allow_newsletter` field set to `True`, or if the field does not exist, the
    Schedule will be filtered out.

    The Schedules QuerySet is used to send recurring nudges emails to users.
    This filter allows excluding users who have opted out of receiving these
    emails.

    Example usage:

    Add the following configurations to your configuration file:

    ```
    OPEN_EDX_FILTERS_CONFIG = {
        "org.openedx.learning.schedule.queryset.requested.v1": {
            "fail_silently": False,
            "pipeline": [
                "nau_openedx_extensions.filters.pipeline.FilterUsersWithAllowedNewsletter",
            ],
        },
    }
    ```
    """

    def run_filter(self, schedules: QuerySet) -> dict:  # pylint: disable=arguments-differ
        """
        Execute filter that filters users with allowed newsletter.

        Arguments:
            schedules (QuerySet): Queryset of schedules to be sent.

        Returns:
            dict: Dictionary with the filtered schedules.
        """
        return {"schedules": schedules.filter(enrollment__user__nauuserextendedmodel__allow_newsletter=True)}


class FilterCertificateExportTab(PipelineStep):
    """
    Add a Certificate export tab to the instructor dashboard.
    """
    def run_filter(self, context, template_name):
        logging.warning("EJECUTANDO FILTRO CERTIFICATE EXPORT")
        course = context["course"]
        template = Template(self.resource_string("static/html/certificate_export.html"))

        # Si necesitas el usuario actual:
        request = get_current_request()
        # Puedes agregar lógica de permisos aquí si lo deseas

        # Puedes actualizar el contexto con datos adicionales si lo necesitas
        context.update({
            "certificate_export_url": getattr(settings, "CERTIFICATE_EXPORT_URL", ""),
            # ...otros datos...
        })

        logging.warning("Sections context: %s", context["sections"])

        html = template.render(Context(context))
        frag = Fragment(html)

        # Si tienes CSS/JS específicos para este tab:
        # frag.add_css(self.resource_string("static/css/certificate_export.css"))
        # frag.add_javascript(self.resource_string("static/js/certificate_export.js"))

        section_data = {
            "fragment": frag,
            "section_key": BLOCK_CATEGORY,
            "section_display_name": _("Certificate Export"),
            "course_id": str(course.id),
            "template_path_prefix": TEMPLATE_ABSOLUTE_PATH,  # <--- Cambia esto
        }
        logging.warning("ANTES DE APPEND: %s", context["sections"])
        context["sections"].append(section_data)
        logging.warning("DESPUES DE APPEND: %s", context["sections"])
        logging.warning("RETURN CONTEXT: %s", context)
        return {
            "context": context,
        }

    def resource_string(self, path):
        """Helper to get resources from the extension package."""
        data = pkg_resources.resource_string(
            "nau_openedx_extensions", path
        )
        return data.decode("utf8")
