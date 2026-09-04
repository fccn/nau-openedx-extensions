"""
Defined filters.
"""

import importlib.resources as resources
import logging
from fnmatch import fnmatch
from urllib.parse import urlencode

from crum import get_current_request, get_current_user
from django.conf import settings
from django.db.models.query import QuerySet
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseAboutRenderStarted, CourseEnrollmentStarted, RenderXBlockStarted
from web_fragments.fragment import Fragment

from nau_openedx_extensions.edxapp_wrapper import site_configuration_helpers as configuration_helpers
from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings
from nau_openedx_extensions.edxapp_wrapper.student import get_enrollment, get_student_course_enrollment_allowed
from nau_openedx_extensions.utils.nif import is_nif_valid

log = logging.getLogger(__name__)

TEMPLATE_ABSOLUTE_PATH = "/instructor_dashboard/"
REQUIRE_PROFILE_FIELDS_SETTING = "filter_enrollment_require_profile_fields"
BLOCK_CATEGORY = "certificate_export"


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


def profile_field_is_filled(user, field_name):
    """
    Whether the user has a usable value for `field_name`.

    Looks the name up on NauUserExtendedModel first and then on the native
    UserProfile. Returns None when the field exists on neither, so the caller can
    tell "not filled" apart from "not a field at all".
    """
    if field_name == "nif":
        # nau_nif already falls back to the citizen card NIF, and a stored but
        # invalid NIF should not count as filled.
        return is_nif_valid(user.nau_nif)

    for source in (getattr(user, "nauuserextendedmodel", None), getattr(user, "profile", None)):
        if source is not None and hasattr(source, field_name):
            return bool(getattr(source, field_name))
    return None


def profile_field_label(field_name):
    """
    Human readable label for a field name, for messages the learner sees.

    Falls back to the field name with underscores turned into spaces, which
    covers native profile fields and anything not declared on the NAU model.
    """
    from django.core.exceptions import FieldDoesNotExist  # pylint: disable=import-outside-toplevel

    from nau_openedx_extensions.custom_registration_form.models import (  # pylint: disable=import-outside-toplevel
        NauUserExtendedModel,
    )

    try:
        return str(NauUserExtendedModel._meta.get_field(field_name).verbose_name)
    except FieldDoesNotExist:
        return field_name.replace("_", " ")


def missing_profile_fields(user, course_key):
    """
    The required profile fields the user has not filled in for this course.

    Returns an empty list when the course does not require any, which is the
    default: a course only gates on profile data if it says so in its advanced
    settings.
    """
    other_course_settings = get_other_course_settings(course_key)
    required_fields = other_course_settings.get("value", {}).get(REQUIRE_PROFILE_FIELDS_SETTING)

    if not required_fields:
        return []

    missing = []
    for field_name in required_fields:
        filled = profile_field_is_filled(user, field_name)
        if filled is None:
            log.warning(
                "Course %s requires the profile field '%s', which does not exist on "
                "NauUserExtendedModel or UserProfile. Ignoring it.",
                course_key,
                field_name,
            )
            continue
        if not filled:
            missing.append(field_name)

    return missing


class FilterEnrollmentRequireProfileFields(PipelineStep):
    """
    Stop the enrollment process if the learner has not filled in the profile fields
    that the course requires.

    This generalizes FilterEnrollmentRequireNIF to the full characterization data
    set of Phase 1 (NIF, employment situation, NUTS, CAE4, plus the native profile
    fields). That filter stays as it is, so courses already using it keep working.

    Which fields block enrollment is set per course, so a course that asks for
    nothing keeps enrolling everyone. Add `filter_enrollment_require_profile_fields`
    to the course advanced settings with the list of field names:

        "filter_enrollment_require_profile_fields": ["nif", "nuts", "cae4"]

    Field names are looked up on NauUserExtendedModel first and then on the native
    UserProfile, so both `nuts` and `year_of_birth` work. A name that matches
    neither is logged and ignored rather than blocking everyone, since a typo in
    the course settings should not lock a course.

    Example usage:
    Add the following configurations to your configuration file:
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.course.enrollment.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.filters.pipeline.FilterEnrollmentRequireProfileFields"
                ]
            }
        }
    """

    def run_filter(self, user, course_key, mode):   # pylint: disable=unused-argument, arguments-differ
        """Filter implementation."""

        missing = missing_profile_fields(user, course_key)

        if missing:
            raise CourseEnrollmentStarted.PreventEnrollment(
                _("Please complete your profile before enrolling in this course. Missing: {fields}.").format(
                    fields=", ".join(profile_field_label(name) for name in missing)
                )
            )

        return {}


def profile_completion_context(course, missing, heading, body_text):
    """
    Context for the profile completion panel, shared by the pages that show it.
    """
    account_url = getattr(settings, "ACCOUNT_MICROFRONTEND_URL", "")
    separator = "&" if "?" in account_url else "?"
    return {
        "heading": heading,
        "body_text": body_text,
        "missing_labels": [profile_field_label(name) for name in missing],
        "account_url": f"{account_url}{separator}{urlencode({'missing': ','.join(missing)})}",
        "course_about_url": f"/courses/{course.id}/about",
    }


class RequireProfileFieldsOnCourseAbout(PipelineStep):
    """
    Replace the course about page with a note listing the profile fields the
    learner still has to fill in.

    This is the visible half of the Phase 1 gate. FilterEnrollmentRequireProfileFields
    stops the enrollment itself; this one tells the learner why and links to the
    account page, instead of letting them sit on a course they cannot enroll in.

    It renders a custom response rather than redirecting on purpose. The course
    about view turns RedirectToPage into CourseAccessRedirect(exc.redirect_to) and
    drops the message, so a redirect arrives at the account page with no
    explanation of why the learner was sent there.

    It reads the same course advanced setting, so a course declares its required
    fields once:

        "filter_enrollment_require_profile_fields": ["nif", "nuts", "cae4"]

    The account link carries the missing field names as a `missing` query
    parameter. The account page does not read it yet, so nothing is highlighted
    there; that needs a change in the frontend component that renders the
    extended profile.

    Example usage:
    Add the following configurations to your configuration file:
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.course_about.render.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.filters.pipeline.RequireProfileFieldsOnCourseAbout"
                ]
            }
        }
    """

    def run_filter(self, context, template_name):   # pylint: disable=arguments-differ
        """Filter implementation."""

        user = get_current_user()
        course = context.get("course")

        if course is None or user is None or not user.is_authenticated:
            return {"context": context, "template_name": template_name}

        missing = missing_profile_fields(user, course.id)

        if not missing:
            return {"context": context, "template_name": template_name}

        account_url = getattr(settings, "ACCOUNT_MICROFRONTEND_URL", "")
        if not account_url:
            # Without somewhere to send the learner the note would be a dead end,
            # so leave the page alone and let the enrollment filter do the blocking.
            log.warning(
                "Course %s requires profile fields but ACCOUNT_MICROFRONTEND_URL is not set, "
                "so the learner cannot be pointed at where to complete them.",
                course.id,
            )
            return {"context": context, "template_name": template_name}

        template_context = profile_completion_context(
            course,
            missing,
            _("Complete your profile to enroll"),
            _("To enroll in this course, please complete the following information:"),
        )
        # There is nowhere to go back to from the about page itself.
        template_context["course_about_url"] = ""

        raise CourseAboutRenderStarted.RenderCustomResponse(
            _("Please complete your profile before enrolling in this course. Missing: {fields}.").format(
                fields=", ".join(template_context["missing_labels"])
            ),
            # The request is passed so the themed stylesheet is picked, not the
            # default one: theme resolution needs the current site.
            response=HttpResponse(render_to_string(
                "profile_completion/required_fields.html",
                template_context,
                request=get_current_request(),
            )),
        )


class RequireProfileFieldsOnXBlockRender(PipelineStep):
    """
    Replace course content with the profile completion panel while the learner is
    missing the fields the course requires.

    Enrollment and the course about page are not enough on their own. A learner
    can already be enrolled, from before the course started requiring the fields
    or through a bulk enrollment, and would then walk straight into the content.
    This is the filter that actually keeps them out of it.

    It reads the same course advanced setting as the other two, so a course still
    declares its required fields once:

        "filter_enrollment_require_profile_fields": ["nif", "nuts", "cae4"]

    Staff are let through, so a course team can always open its own course.

    Example usage:
    Add the following configurations to your configuration file:
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.xblock.render.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.filters.pipeline.RequireProfileFieldsOnXBlockRender"
                ]
            }
        }
    """

    def run_filter(self, context, student_view_context):   # pylint: disable=arguments-differ
        """Filter implementation."""

        unchanged = {"context": context, "student_view_context": student_view_context}

        user = get_current_user()
        course = context.get("course")

        if course is None or user is None or not user.is_authenticated:
            return unchanged

        if context.get("staff_access"):
            return unchanged

        missing = missing_profile_fields(user, course.id)

        if not missing:
            return unchanged

        if not getattr(settings, "ACCOUNT_MICROFRONTEND_URL", ""):
            log.warning(
                "Course %s requires profile fields but ACCOUNT_MICROFRONTEND_URL is not set, "
                "so the learner cannot be pointed at where to complete them.",
                course.id,
            )
            return unchanged

        template_context = profile_completion_context(
            course,
            missing,
            _("Complete your profile to continue"),
            _("To continue with the course, please complete the following information:"),
        )

        # The view wraps this in a Fragment, so it takes markup rather than an
        # HttpResponse, unlike the course about filter above.
        raise RenderXBlockStarted.RenderCustomResponse(
            _("Please complete your profile to open this course. Missing: {fields}.").format(
                fields=", ".join(template_context["missing_labels"])
            ),
            response=render_to_string("profile_completion/_panel.html", template_context),
        )


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
