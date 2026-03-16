"""
SSO Partner Integration course enrollment filters.

This module contains filters for validating SSO partner linkage during
course enrollment.
"""

import logging

from django.apps import apps
from django.utils.translation import gettext as _
from openedx_filters import PipelineStep
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.edxapp_wrapper.course_module import get_other_course_settings

logger = logging.getLogger(__name__)


class FilterSSOPartnerAccountLink(PipelineStep):
    """
    Validate that a user attempting to enroll has a completed SSO account link
    with a partner that has access to the course.

    This filter checks:
    1. If the user has an SSOPartnerIntegration record (linked account).
    2. If the partner client's base_security_scope allows access to the course.

    If either check fails, enrollment is prevented with a Portuguese error message.

    The partner's base_security_scope defines which courses they can access,
    and is validated against the CourseOverview model fields.

    To activate it, the course needs to have the setting `filter_enroll_only_if_sso_completed`
    set to `true` inside the course other settings on the advanced settings.

    Example usage:

    Add the following configurations to your configuration file:

        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.course.enrollment.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.partner_integration.course_filters.FilterSSOPartnerAccountLink"
                ]
            }
        }
    """

    def run_filter(self, user, course_key, mode):  # pylint: disable=unused-argument, arguments-differ
        """
        Filter implementation.

        Validates SSO partner account link and partner course access.
        Only activated if the course has `filter_enroll_only_if_sso_completed`
        set to true in its advanced settings.

        Args:
            user: The user attempting to enroll.
            course_key: The course key for the course being enrolled in.
            mode: The enrollment mode (unused).

        Returns:
            Empty dict if validation passes or filter is not active.

        Raises:
            CourseEnrollmentStarted.PreventEnrollment: If user is not linked to a partner
                or the partner doesn't have access to the course.
        """
        other_course_settings = get_other_course_settings(course_key)
        filter_enabled = other_course_settings.get("value", {}).get(
            "filter_enroll_only_if_sso_completed"
        )

        if not filter_enabled:
            return {}

        try:
            SSOPartnerIntegration = apps.get_model(
                "nau_openedx_extensions",
                "SSOPartnerIntegration"
            )
        except LookupError:
            logger.error("SSOPartnerIntegration model not found")
            return {}

        try:
            sso_record = SSOPartnerIntegration.objects.get(user=user)
        except SSOPartnerIntegration.DoesNotExist as exc:
            logger.warning(
                f"User {user.id} ({user.username}) has no SSO partner integration record"
            )
            exception_msg = _(
                "The SSO partner integration has not been completed. "
                "Please complete the SSO partner integration before enrolling."
            )
            raise CourseEnrollmentStarted.PreventEnrollment(exception_msg) from exc

        partner_client = sso_record.partner_client
        base_security_scope = partner_client.query_security_scope.get("base_security_scope", {})

        if not base_security_scope:
            logger.warning(
                f"Partner {partner_client.name} has no base_security_scope configured"
            )
            exception_msg = _(
                "The partner integration has no access configured for any course. "
                "Please contact support."
            )
            raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)

        if not FilterSSOPartnerAccountLink._is_course_allowed_for_partner(course_key, base_security_scope):
            logger.warning(
                f"Partner {partner_client.name} does not have access to course {course_key}"
            )
            exception_msg = _(
                "The partner integration does not have permission to enroll users in this course. "
                "Please contact support."
            )
            raise CourseEnrollmentStarted.PreventEnrollment(exception_msg)

        logger.info(
            f"User {user.id} ({user.username}) validated for enrollment in {course_key} "
            f"via partner {partner_client.name}"
        )
        return {}

    @staticmethod
    def _is_course_allowed_for_partner(course_key, base_security_scope):
        """
        Check if a course is allowed by the partner's base_security_scope.

        The base_security_scope uses Django ORM lookup syntax to filter CourseOverview.
        This method applies the security scope filters to determine if the course is allowed.

        Args:
            course_key: The course key to validate.
            base_security_scope: A dictionary of Django ORM filters for CourseOverview.

        Returns:
            True if the course matches the security scope, False otherwise.
        """
        try:
            CourseOverview = apps.get_model("course_overviews", "CourseOverview")
        except LookupError:
            logger.error("CourseOverview model not found")
            return False

        try:
            query = CourseOverview.objects.filter(**base_security_scope)
            course_exists = query.filter(id=course_key).exists()
            return course_exists
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                f"Error validating course {course_key} against security scope: {e}"
            )
            return False
