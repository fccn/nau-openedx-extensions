"""
Tests for the pipeline module used in nau_openex_extensions
"""

import json
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from django.test.utils import override_settings
from django_mock_queries.query import MockModel, MockSet
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseEnrollmentStarted

from nau_openedx_extensions.filters.pipeline import (
    FilterCertificateExportTab,
    FilterEnrollmentByDomain,
    FilterEnrollmentRequireNIF,
    FilterUsersWithAllowedNewsletter,
)


@override_settings(
    NAU_STUDENT_MODULE=(
        "nau_openedx_extensions.edxapp_wrapper.backends.student_l_v1_tests"
    ),
)
class FilterEnrollmentByDomainTest(TestCase):
    """
    Test the FilterEnrollmentByDomain that prevent enrollment if the email domain is not allowed.
    """

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_for_allowed_domain(self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when user has a domain that is allowed in the other course settings.

        Expected result:
        - The get other course settings is called once with the course key.
        - The other_course_settings.get is called once with value and {}
        - The other_course_settings.get calls get with filter_enrollment_by_domain_list and []
        - The function fnmatch is called with a user_domain and a domain
        - The filter returns {} that means that the user is allowed to enroll.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["example.com"]
        other_course_settings = Mock()
        get_other_course_settings_mock.return_value = other_course_settings
        other_course_settings_get = Mock()
        other_course_settings.get.return_value = other_course_settings_get
        other_course_settings_get.get.return_value = allowed_domains_list
        fnmatch_mock.return_value = True

        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)

        get_other_course_settings_mock.assert_called_once_with(course_key)
        other_course_settings.get.assert_called_once_with("value", {})
        other_course_settings_get.get.assert_called_once_with("filter_enrollment_by_domain_list")
        fnmatch_mock.assert_not_called()
        self.assertEqual(response, {})

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_for_allowed_domain_with_subdomain(
            self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when user has a subdomain that is allowed in the other course settings.

        Expected result:
        - The fnmatch is called with the all subdomain and a domain
        - The filter returns {} that means that the user is allowed to enroll.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["example.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        user = MagicMock(email="example@subdomain.example.com")
        fnmatch_mock.return_value = True
        user_domain = user.email.split("@")[1]

        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)

        fnmatch_mock.assert_called_once_with(user_domain, f"*.{allowed_domains_list[0]}")
        self.assertEqual(response, {})

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_for_no_other_course_setting(self, get_other_course_settings_mock, fnmatch_mock):
        """Test the filter when the course dont have other course settings for filter_enrollment_by_domain_list.

        Expected result:
        - The fnmatch not called
        - The filter returns {} that means that the user is allowed to enroll."""
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        get_other_course_settings_mock.return_value = {}

        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)

        fnmatch_mock.assert_not_called()
        self.assertEqual(response, {})

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_not_allowed_to_enroll(self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when exists the other course settings with filter_enrollment_by_domain_list,
        but the user is not allowed to enroll because the domain is not in the settings.

        Expected result:
        - PreventEnrollment exception has raised
        - The fnmatch has been called once with the user domain and a domain
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["test.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        fnmatch_mock.return_value = False
        user_domain = user.email.split("@")[1]

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
            fnmatch_mock.assert_called_once_with(user_domain, f"*.{allowed_domains_list[0]}")

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_not_allowed_to_enroll_similar_email(self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when exists the other course settings with filter_enrollment_by_domain_list,
        but the user is not allowed to enroll because the domain is not in the settings.
        Check it won't match for very similar domains, but it isn't a subdomain.

        Expected result:
        - PreventEnrollment exception has raised
        - The fnmatch has been called once with the user domain and a domain
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["xample.com", "eexample.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        fnmatch_mock.return_value = False
        user_domain = user.email.split("@")[1]

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
            fnmatch_mock.assert_called_once_with(user_domain, f"*.{allowed_domains_list[0]}")

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    @override_settings(PLATFORM_NAME='NAU')
    def test_require_user_to_activate_account_for_filter_enrollment_by_domain(
            self, get_other_course_settings_mock):
        """
        Test the filter when the course has a configuration in the other course settings
        that should filter enrollment by user email domain,
        the user email matches one of the allowed domains,
        but he hasn't activated its account.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=False)
        mode = "audit"

        allowed_domains_list = ["xample.com", "example.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as pe:
            FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
        self.assertEqual(pe.exception.message, (
            "You need to activate your account before you can enroll in the course. "
            "Check your example@example.com inbox for an account activation link from NAU."
        ))

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_require_user_to_activate_account_for_enrollment_course_no_config_user_active(
            self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when the course hasn't a configuration in the other course settings
        and the user has an activated account.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        get_other_course_settings_mock.return_value = {"value": {}}
        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
        self.assertEqual(response, {})
        fnmatch_mock.assert_not_called()

    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_require_user_to_activate_account_for_enrollment_course_no_config_user_inactive(
            self, get_other_course_settings_mock, fnmatch_mock):
        """
        Test the filter when the course has a configuration in the other course settings
        and the user hasn't an activated account.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=False)
        mode = "audit"

        get_other_course_settings_mock.return_value = {"value": {}}
        response = FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
        self.assertEqual(response, {})
        fnmatch_mock.assert_not_called()

    @patch('nau_openedx_extensions.filters.pipeline.get_student_course_enrollment_allowed')
    @patch('nau_openedx_extensions.filters.pipeline.fnmatch')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_email_not_in_allowed_domains_to_enroll_but_with_course_enrollment_allowed(
            self, get_other_course_settings_mock, fnmatch_mock, get_student_course_enrollment_allowed_mock):
        """
        Test the filter when the user email in not in the allowed domains for self enroll, but the
        user email have been manualy added as a course enrollment allowed.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=True)
        mode = "audit"

        allowed_domains_list = ["xample.com", "eexample.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}
        get_student_course_enrollment_allowed_mock.return_value = object()

        FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)

        get_student_course_enrollment_allowed_mock.assert_called_once_with(user, course_key)
        fnmatch_mock.assert_not_called()

    @override_settings(PLATFORM_NAME='NAU')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_inactive_user_with_email_not_in_allowed_domains(self, get_other_course_settings_mock):
        """
        Test the filter when the user is inactive and the user email domain isn't an allowed
        domain and check that it failing with the error message related that the user needs to
        activate their account.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MagicMock(email="example@example.com", is_active=False)
        mode = "audit"

        allowed_domains_list = ["xample.com", "eexample.com"]
        get_other_course_settings_mock.return_value = {
            "value": {"filter_enrollment_by_domain_list": allowed_domains_list}}

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as pe:
            FilterEnrollmentByDomain.run_filter(self, user, course_key, mode)
        self.assertEqual(pe.exception.message, (
            "You need to activate your account before you can enroll in the course. "
            "Check your example@example.com inbox for an account activation link from NAU."
        ))


class FilterEnrollmentRequireNIFTest(TestCase):
    """
    Test the FilterEnrollmentRequireNIF class that prevents enrollment if the user doesn't have a NIF
    on its account.
    """

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_with_valid_nif(self, get_other_course_settings_mock):
        """
        Test the filter when user has a valid NIF.

        Expected result:
        - The get other course settings is called once with the course key.
        - The other_course_settings.get is called once with value and {}
        - The other_course_settings.get calls get with filter_enrollment_require_nif and True
        - The filter returns {} that means that the user is allowed to enroll.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MockModel(email="example@example.com", is_active=True, nau_nif='123456789')
        mode = "audit"

        other_course_settings = Mock()
        get_other_course_settings_mock.return_value = other_course_settings
        other_course_settings_get = Mock()
        other_course_settings.get.return_value = other_course_settings_get
        other_course_settings_get.get.return_value = True

        response = FilterEnrollmentRequireNIF.run_filter(self, user, course_key, mode)

        get_other_course_settings_mock.assert_called_once_with(course_key)
        other_course_settings.get.assert_called_once_with("value", {})
        other_course_settings_get.get.assert_called_once_with("filter_enrollment_require_nif")
        self.assertEqual(response, {})

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_no_nif(self, get_other_course_settings_mock):
        """
        Test the filter when user has't a NIF.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MockModel(email="example@example.com", is_active=True, nau_nif=None)
        mode = "audit"

        other_course_settings = Mock()
        get_other_course_settings_mock.return_value = other_course_settings
        other_course_settings_get = Mock()
        other_course_settings.get.return_value = other_course_settings_get
        other_course_settings_get.get.return_value = True

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as pe:
            FilterEnrollmentRequireNIF.run_filter(self, user, course_key, mode)

        get_other_course_settings_mock.assert_called_once_with(course_key)
        other_course_settings.get.assert_called_once_with("value", {})
        other_course_settings_get.get.assert_called_once_with("filter_enrollment_require_nif")
        self.assertEqual(pe.exception.message, (
            "You need to associate Autenticação Gov to your account or add NIF to your account."
        ))

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_user_is_allowed_to_enroll_with_invalid_nif(self, get_other_course_settings_mock):
        """
        Test the filter when user has an invalid NIF, for example before introducing the NIF
        validation feature.
        """
        course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        user = MockModel(email="example@example.com", is_active=True, nau_nif='999')
        mode = "audit"

        other_course_settings = Mock()
        get_other_course_settings_mock.return_value = other_course_settings
        other_course_settings_get = Mock()
        other_course_settings.get.return_value = other_course_settings_get
        other_course_settings_get.get.return_value = True

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as pe:
            FilterEnrollmentRequireNIF.run_filter(self, user, course_key, mode)

        get_other_course_settings_mock.assert_called_once_with(course_key)
        other_course_settings.get.assert_called_once_with("value", {})
        other_course_settings_get.get.assert_called_once_with("filter_enrollment_require_nif")
        self.assertEqual(pe.exception.message, (
            "You need to associate Autenticação Gov to your account or add NIF to your account."
        ))


class FilterUsersWithAllowedNewsletterTest(TestCase):
    """
    Test the FilterUsersWithAllowedNewsletter class that filters users who have allowed newsletters.
    """

    def test_run_filter(self):
        """
        Test that the filter returns only schedules for users who have allowed newsletters.

        Expected result:
        - The filter returns a dictionary with the key schedules and a queryset of schedules.
        - The schedules queryset has only one schedule that has a user with allow_newsletter=True.
        - The other schedules that have a user with allow_newsletter=False or without allow_newsletter
            are not in the queryset.
        """
        mock_schedules = MockSet(
            MockModel(
                mock_name="allow_newsletter_true",
                enrollment=MockModel(user=MockModel(nauuserextendedmodel=MockModel(allow_newsletter=True))),
            ),
            MockModel(
                mock_name="allow_newsletter_false",
                enrollment=MockModel(user=MockModel(nauuserextendedmodel=MockModel(allow_newsletter=False))),
            ),
            MockModel(mock_name="without_allow_newsletter", enrollment=MockModel(user=MockModel())),
        )

        result = FilterUsersWithAllowedNewsletter.run_filter(self, mock_schedules)

        self.assertIsInstance(result, dict)
        self.assertIn("schedules", result)
        self.assertEqual(len(result["schedules"]), 1)
        self.assertEqual(result["schedules"][0].mock_name, "allow_newsletter_true")


class FilterCertificateExportTabTest(TestCase):
    """
    Test the FilterCertificateExportTab class that adds the NAU Reports tab to the instructor dashboard.
    """

    def setUp(self):
        """Set up a course whose org contains an underscore, as report file names can."""
        self.course = MagicMock(id=CourseKey.from_string("course-v1:Partner_2+CP02+2026"))
        self.context = {"course": self.course, "sections": []}
        self.filter_step = FilterCertificateExportTab(
            "org.openedx.learning.instructor.dashboard.render.started.v1", []
        )

    def _run_filter(self):
        """Run the filter with URL resolution and template rendering mocked."""
        with patch(
            "nau_openedx_extensions.filters.pipeline.reverse",
            side_effect=lambda name, kwargs: f"/{name}",
        ) as reverse_mock:
            with patch(
                "nau_openedx_extensions.filters.pipeline.render_to_string",
                return_value="<div>NAU Reports</div>",
            ) as render_to_string_mock:
                result = self.filter_step.run_filter(context=self.context, template_name="instructor_dashboard.html")
        return result, reverse_mock, render_to_string_mock

    def test_run_filter_adds_nau_reports_section(self):
        """
        Test that the filter appends the NAU Reports section to the instructor dashboard.

        Expected result:
        - One section with the certificate_export key, the "NAU Reports" name and the course id.
        - Its fragment holds the rendered tab template plus the tab CSS and JavaScript.
        """
        result, _, render_to_string_mock = self._run_filter()

        self.assertEqual(len(result["context"]["sections"]), 1)
        section = result["context"]["sections"][0]
        self.assertEqual(section["section_key"], "certificate_export")
        self.assertEqual(section["section_display_name"], "NAU Reports")
        self.assertEqual(section["course_id"], "course-v1:Partner_2+CP02+2026")
        self.assertEqual(section["template_path_prefix"], "/instructor_dashboard/")
        render_to_string_mock.assert_called_once_with("certificate_export/certificate_export.html", self.context)
        self.assertEqual(section["fragment"].body_html(), "<div>NAU Reports</div>")
        self.assertEqual(
            [resource.mimetype for resource in section["fragment"].resources],
            ["text/css", "application/javascript"],
        )

    def test_run_filter_passes_report_endpoints_and_messages_to_template(self):
        """
        Test that each report button and the downloads list get their endpoint URL for the course.

        Expected result:
        - Each URL is resolved from its URL name with the course id (and "/csv" for the profile report).
        - The messages shown by the JavaScript for each report are in the context.
        """
        result, reverse_mock, _ = self._run_filter()
        context = result["context"]

        expected_urls = {
            "certificate_export_url": ("nau-openedx-extensions:nau_export_certificates_csv", {}),
            "certificate_export_pdf_url": ("nau-openedx-extensions:nau_export_certificates_pdf", {}),
            "grade_report_url": ("calculate_grades_csv", {}),
            "profile_report_url": ("get_students_features", {"csv": "/csv"}),
            "survey_report_url": ("nau-openedx-extensions:nau_export_surveys_csv", {}),
            "report_downloads_url": ("list_report_downloads", {}),
        }
        for context_key, (url_name, extra_kwargs) in expected_urls.items():
            with self.subTest(context_key=context_key):
                self.assertEqual(context[context_key], f"/{url_name}")
                reverse_mock.assert_any_call(url_name, kwargs={"course_id": self.course.id, **extra_kwargs})

        for message_key in (
            "grade_report_success",
            "grade_report_failure",
            "profile_report_success",
            "profile_report_failure",
            "survey_report_success",
            "survey_report_failure",
            "report_downloads_empty",
            "report_downloads_failure",
        ):
            with self.subTest(message_key=message_key):
                self.assertTrue(context[message_key])

    def test_run_filter_report_downloads_prefixes_select_only_tab_reports(self):
        """
        Test that the file name prefixes given to the JavaScript list only this tab's reports.

        The JavaScript keeps the report files whose name starts with one of the prefixes. Report
        files are named "{org}_{course}_{run}_{report}_{timestamp}" and the org can contain underscores.

        Expected result:
        - One prefix per tab report, built with the platform course file name prefix.
        - Certificates (CSV and PDF ZIP), grade (and its errors), profile and survey reports are listed.
        - Other reports, even with similar names, are not listed.
        """
        result, _, _ = self._run_filter()
        prefixes = json.loads(result["context"]["report_downloads_prefixes"])

        self.assertEqual(prefixes, [
            "Partner_2_CP02_2026_export_course_certificates_",
            "Partner_2_CP02_2026_grade_report_",
            "Partner_2_CP02_2026_student_profile_info_",
            "Partner_2_CP02_2026_survey_report_",
        ])
        listed_by_file_name = {
            "Partner_2_CP02_2026_export_course_certificates_2026-09-11-1000.csv": True,
            "Partner_2_CP02_2026_export_course_certificates_pdfs_2026-09-11-1001.zip": True,
            "Partner_2_CP02_2026_grade_report_2026-09-11-0909.csv": True,
            "Partner_2_CP02_2026_grade_report_err_2026-09-11-0909.csv": True,
            "Partner_2_CP02_2026_student_profile_info_2026-09-11-0907.csv": True,
            "Partner_2_CP02_2026_survey_report_2026-09-11-1017.csv": True,
            "Partner_2_CP02_2026_problem_grade_report_2026-09-11-0908.csv": False,
            "Partner_2_CP02_2026_course_survey_results_2026-09-11-0959.csv": False,
            "Partner_2_CP02_2026_anonymized_ids_2026-09-11-0900.csv": False,
        }
        for file_name, listed in listed_by_file_name.items():
            with self.subTest(file_name=file_name):
                self.assertEqual(any(file_name.startswith(prefix) for prefix in prefixes), listed)
