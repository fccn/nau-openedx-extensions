"""
Defined filters.
"""

import importlib.resources as resources
import json
from fnmatch import fnmatch

from django.conf import settings
from django.db.models.query import QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseEnrollmentStarted
from web_fragments.fragment import Fragment

from nau_openedx_extensions.edxapp_wrapper import site_configuration_helpers as configuration_helpers
from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings
from nau_openedx_extensions.edxapp_wrapper.student import get_enrollment, get_student_course_enrollment_allowed
from nau_openedx_extensions.utils.nif import is_nif_valid

TEMPLATE_ABSOLUTE_PATH = "/instructor_dashboard/"
BLOCK_CATEGORY = "certificate_export"
NAU_REPORTS_BLOCK_CATEGORY = "nau_reports"
# Names of the reports listed in the NAU Reports tab, as stored in the report store
# ("{course_prefix}_{name}_{timestamp}"). Matching by prefix also lists the certificates
# ZIP ("export_course_certificates_pdfs") and the grade report errors ("grade_report_err").
NAU_REPORTS_TAB_REPORT_NAMES = ("export_course_certificates", "grade_report", "student_profile_info", "survey_report")


class FilterEnrollmentByDomain(PipelineStep):   # pylint: disable=too-few-public-methods
    """
    Stop enrollment process raising PreventEnrollment exception if the user has an email
    with a domain that is not in those allowed by a course in DomainsAllowedPerCourse.

    It also allows instructor to override the filter. The user can enroll even if its email
    domain doesn't be one of the allowed if the instructor has added its email as one of the
    Course Enrolment Allowed. A race condition can raise an error, if the user account already
    exist and is inactive, in this case the instructor couldn't add manually the custom user to
    the course. If this happens, the user needs to activate their account before the instructor
    could create the enrollment.

    To activate it, the course needs to have the setting `filter_enrollment_by_domain_list` set
    to a list of email domains inside the course other settings on the advanced settings.

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
        domains_allowed = other_course_settings.get("value", {}).get("filter_enrollment_by_domain_list")

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


class FilterEnrollmentRequireNIF(PipelineStep):
    """
    Stop enrollment process raising PreventEnrollment exception if the user has not
    a NIF and/or CC NIF on its account.
    This makes the course enrollment process to be blocked until the user fills in
    a NIF.
    This filter needs to be configured on the course level, so it can be
    configured on the course settings.

    To activate it, the course needs to have the setting `filter_enrollment_require_nif` with
    a value to 'true' inside the course other settings on the advanced settings.

    Example usage:
    Add the following configurations to your configuration file:
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.course.enrollment.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.filters.pipeline.FilterEnrollmentRequireNIF"
                ]
            }
        }
    """

    def run_filter(self, user, course_key, mode):   # pylint: disable=unused-argument, arguments-differ
        """Filter implementation."""

        other_course_settings = get_other_course_settings(course_key)
        filter_by_nif = other_course_settings.get("value", {}).get("filter_enrollment_require_nif")
        if filter_by_nif:
            # use the 'nau_nif' attr that already has a decorator to get the NIF
            nif = user.nau_nif
            if not is_nif_valid(nif):
                exception_msg = _(
                    "You need to associate Autenticação Gov to your account or add NIF to your account."
                )
                raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)

        return {}


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

    def run_filter(self, context, template_name):  # pylint: disable=unused-argument, arguments-differ
        """
        Add a Certificate export tab to the instructor dashboard.

        Args:
            context (dict): The context of the template.
            template_name (str): The name of the template.

        Returns:
            dict: The context of the template.
        """
        course = context["course"]

        context.update(
            {
                "certificate_export_url": reverse(
                    "nau-openedx-extensions:nau_export_certificates_csv", kwargs={"course_id": course.id}
                ),
                "certificate_export_pdf_url": reverse(
                    "nau-openedx-extensions:nau_export_certificates_pdf", kwargs={"course_id": course.id}
                ),
                "course": course,
                # Add translated messages for JavaScript
                "csv_success": _("CSV export task started successfully!"),
                "csv_failure": _("Failed to start CSV export task."),
                "zip_success": _("ZIP export task started successfully!"),
                "zip_failure": _("Failed to start ZIP export task."),
                "error_msg": _("An unexpected error occurred. Please try again later."),
            }
        )

        # Render the template using Django's template loader
        html = render_to_string("certificate_export/certificate_export.html", context)

        frag = Fragment(html)
        frag.add_css(self.resource_string("static/nau_openedx_extensions/css/certificate_export.css"))
        frag.add_javascript(self.resource_string("static/nau_openedx_extensions/js/certificate_export.js"))

        section_data = {
            "fragment": frag,
            "section_key": BLOCK_CATEGORY,
            "section_display_name": _("Certificate Export"),
            "course_id": str(course.id),
            "template_path_prefix": TEMPLATE_ABSOLUTE_PATH,
        }

        context["sections"].append(section_data)

        return {
            "context": context,
        }

    def resource_string(self, path):
        """Helper to get resources from the extension package."""
        data = resources.files("nau_openedx_extensions").joinpath(path).read_bytes()
        return data.decode("utf8")


class FilterNauReportsTab(PipelineStep):
    """
    Add the NAU Reports tab to the instructor dashboard.

    The tab gathers the reports NAU uses (certificates, grades, profile information and the
    Survey components responses), each with a button to generate it, and lists the generated
    files available for download.

    Example usage:

    Add the following configurations to your configuration file:

    ```
    OPEN_EDX_FILTERS_CONFIG = {
        "org.openedx.learning.instructor.dashboard.render.started.v1": {
            "fail_silently": False,
            "pipeline": [
                "nau_openedx_extensions.filters.pipeline.FilterNauReportsTab",
            ],
        },
    }
    ```
    """

    def run_filter(self, context, template_name):  # pylint: disable=unused-argument, arguments-differ
        """
        Add the NAU Reports tab to the instructor dashboard.

        Args:
            context (dict): The context of the template.
            template_name (str): The name of the template.

        Returns:
            dict: The context of the template.
        """
        # pylint: disable=import-outside-toplevel
        from common.djangoapps.util.file import course_filename_prefix_generator

        course = context["course"]
        course_prefix = course_filename_prefix_generator(course.id)

        context.update(
            {
                "certificate_export_url": reverse(
                    "nau-openedx-extensions:nau_export_certificates_csv", kwargs={"course_id": course.id}
                ),
                "certificate_export_pdf_url": reverse(
                    "nau-openedx-extensions:nau_export_certificates_pdf", kwargs={"course_id": course.id}
                ),
                "grade_report_url": reverse("calculate_grades_csv", kwargs={"course_id": course.id}),
                "profile_report_url": reverse(
                    "get_students_features", kwargs={"course_id": course.id, "csv": "/csv"}
                ),
                "survey_report_url": reverse(
                    "nau-openedx-extensions:nau_export_surveys_csv", kwargs={"course_id": course.id}
                ),
                "report_downloads_url": reverse("list_report_downloads", kwargs={"course_id": course.id}),
                # File name prefixes the JavaScript uses to list only this tab's reports
                "report_downloads_prefixes": json.dumps(
                    [f"{course_prefix}_{name}_" for name in NAU_REPORTS_TAB_REPORT_NAMES]
                ),
                "course": course,
                # Add translated messages for JavaScript
                "csv_success": _("CSV export task started successfully!"),
                "csv_failure": _("Failed to start CSV export task."),
                "zip_success": _("ZIP export task started successfully!"),
                "zip_failure": _("Failed to start ZIP export task."),
                "grade_report_success": _("Grade report task started successfully!"),
                "grade_report_failure": _("Failed to start grade report task."),
                "profile_report_success": _("Profile information report task started successfully!"),
                "profile_report_failure": _("Failed to start profile information report task."),
                "survey_report_success": _("Survey report task started successfully!"),
                "survey_report_failure": _("Failed to start survey report task."),
                "report_downloads_empty": _("No reports have been generated yet."),
                "report_downloads_failure": _("Failed to load the reports available for download."),
                "error_msg": _("An unexpected error occurred. Please try again later."),
            }
        )

        # Render the template using Django's template loader
        html = render_to_string("nau_reports/nau_reports.html", context)

        frag = Fragment(html)
        frag.add_css(self.resource_string("static/nau_openedx_extensions/css/nau_reports.css"))
        frag.add_javascript(self.resource_string("static/nau_openedx_extensions/js/nau_reports.js"))

        section_data = {
            "fragment": frag,
            "section_key": NAU_REPORTS_BLOCK_CATEGORY,
            "section_display_name": _("NAU Reports"),
            "course_id": str(course.id),
            "template_path_prefix": TEMPLATE_ABSOLUTE_PATH,
        }

        context["sections"].append(section_data)

        return {
            "context": context,
        }

    def resource_string(self, path):
        """Helper to get resources from the extension package."""
        data = resources.files("nau_openedx_extensions").joinpath(path).read_bytes()
        return data.decode("utf8")
