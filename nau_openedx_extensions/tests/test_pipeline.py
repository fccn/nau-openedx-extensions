"""
Tests for the pipeline module used in nau_openex_extensions
"""

import re
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase
from django.test.utils import override_settings
from django.utils import translation
from django_mock_queries.query import MockModel, MockSet
from opaque_keys.edx.keys import CourseKey
from openedx_filters.learning.filters import CourseAboutRenderStarted, CourseEnrollmentStarted, RenderXBlockStarted

from nau_openedx_extensions.filters.pipeline import (
    FilterEnrollmentByDomain,
    FilterEnrollmentRequireNIF,
    FilterEnrollmentRequireProfileFields,
    FilterUsersWithAllowedNewsletter,
    RequireProfileFieldsOnCourseAbout,
    RequireProfileFieldsOnXBlockRender,
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


class FilterEnrollmentRequireProfileFieldsTest(TestCase):
    """
    Test FilterEnrollmentRequireProfileFields, which blocks enrollment when the
    learner is missing the profile fields the course asks for.
    """

    # The filter returns an empty dict to let the enrollment through. Compared
    # against a name rather than a `{}` literal so the assertions stay exact:
    # `not response` would also pass if the filter returned None by mistake.
    ENROLLMENT_ALLOWED = {}

    def setUp(self):
        super().setUp()
        self.course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        self.mode = "audit"

    @staticmethod
    def _course_settings(required_fields):
        """Build the other_course_settings shape the filter reads."""
        return {"value": {"filter_enrollment_require_profile_fields": required_fields}}

    class FakeModel:
        """
        Plain stand-in for a model instance.

        MockModel cannot be used here: it answers hasattr() for any name and
        returns None, so a field that does not exist would look present but
        empty. Telling those two apart is exactly what this filter does.
        """

        def __init__(self, **fields):
            self.__dict__.update(fields)

    def _user(self, nau_nif=None, profile_fields=None, **extended_fields):
        """A user whose NAU extended model and native profile carry the given fields."""
        return self.FakeModel(
            email="example@example.com",
            is_active=True,
            nau_nif=nau_nif,
            nauuserextendedmodel=self.FakeModel(**extended_fields),
            profile=self.FakeModel(**(profile_fields or {})),
        )

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_course_without_the_setting_enrolls_everyone(self, get_other_course_settings_mock):
        get_other_course_settings_mock.return_value = {"value": {}}
        user = self._user(nuts=None, cae4=None)

        response = FilterEnrollmentRequireProfileFields.run_filter(self, user, self.course_key, self.mode)

        assert response == self.ENROLLMENT_ALLOWED

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_empty_list_enrolls_everyone(self, get_other_course_settings_mock):
        get_other_course_settings_mock.return_value = self._course_settings([])
        user = self._user(nuts=None)

        response = FilterEnrollmentRequireProfileFields.run_filter(self, user, self.course_key, self.mode)

        assert response == self.ENROLLMENT_ALLOWED

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_all_required_fields_filled(self, get_other_course_settings_mock):
        get_other_course_settings_mock.return_value = self._course_settings(["nuts", "cae4"])
        user = self._user(nuts="norte_cavado", cae4="tertiary_education")

        response = FilterEnrollmentRequireProfileFields.run_filter(self, user, self.course_key, self.mode)

        assert response == self.ENROLLMENT_ALLOWED

    @translation.override("en")
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_missing_field_blocks_enrollment(self, get_other_course_settings_mock):
        get_other_course_settings_mock.return_value = self._course_settings(["nuts", "cae4"])
        user = self._user(nuts="norte_cavado", cae4=None)

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment) as blocked:
            FilterEnrollmentRequireProfileFields.run_filter(self, user, self.course_key, self.mode)

        # The message names what is missing, so the learner knows what to go and fill in.
        assert blocked.exception.message == (
            "Please complete your profile before enrolling in this course. Missing: CAE4."
        )

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_nif_is_validated_not_just_present(self, get_other_course_settings_mock):
        # A stored but invalid NIF must not count as filled, same as in
        # FilterEnrollmentRequireNIF.
        get_other_course_settings_mock.return_value = self._course_settings(["nif"])
        user = self._user(nau_nif="111111111")

        with self.assertRaises(CourseEnrollmentStarted.PreventEnrollment):
            FilterEnrollmentRequireProfileFields.run_filter(self, user, self.course_key, self.mode)

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_valid_nif_passes(self, get_other_course_settings_mock):
        get_other_course_settings_mock.return_value = self._course_settings(["nif"])
        user = self._user(nau_nif="123456789")

        response = FilterEnrollmentRequireProfileFields.run_filter(self, user, self.course_key, self.mode)

        assert response == self.ENROLLMENT_ALLOWED

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_native_profile_field_is_read_from_the_profile(self, get_other_course_settings_mock):
        get_other_course_settings_mock.return_value = self._course_settings(["year_of_birth"])
        user = self._user(profile_fields={"year_of_birth": 1990})

        response = FilterEnrollmentRequireProfileFields.run_filter(self, user, self.course_key, self.mode)

        assert response == self.ENROLLMENT_ALLOWED

    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_unknown_field_is_ignored_instead_of_blocking(self, get_other_course_settings_mock):
        # A typo in the course settings should not lock the course for everyone.
        get_other_course_settings_mock.return_value = self._course_settings(["nutz"])
        user = self._user(nuts="norte_cavado")

        response = FilterEnrollmentRequireProfileFields.run_filter(self, user, self.course_key, self.mode)

        assert response == self.ENROLLMENT_ALLOWED


class RequireProfileFieldsOnCourseAboutTest(TestCase):
    """
    Test RequireProfileFieldsOnCourseAbout, which replaces the course about page
    with a note listing the profile fields the learner still has to fill in.
    """

    ACCOUNT_URL = "http://apps.example.com/account/"

    def setUp(self):
        super().setUp()
        self.course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        self.template_name = "courseware/course_about.html"

    class FakeModel:
        """Plain stand-in, for the same reason as in the filter test above."""

        def __init__(self, **fields):
            self.__dict__.update(fields)

    def _context(self):
        return {
            "course": self.FakeModel(id=self.course_key, display_name_with_default="Demo Course"),
            "course_target": "/courses/course-v1:Demo+DemoX+Demo_Course/about",
        }

    def _user(self, is_authenticated=True, **extended_fields):
        return self.FakeModel(
            is_authenticated=is_authenticated,
            nau_nif=None,
            nauuserextendedmodel=self.FakeModel(**extended_fields),
            profile=self.FakeModel(),
        )

    @staticmethod
    def _course_settings(required_fields):
        return {"value": {"filter_enrollment_require_profile_fields": required_fields}}

    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_course_without_the_setting_renders_normally(self, settings_mock, user_mock):
        settings_mock.return_value = {"value": {}}
        user_mock.return_value = self._user(nuts=None)
        context = self._context()

        response = RequireProfileFieldsOnCourseAbout.run_filter(self, context, self.template_name)

        assert response == {"context": context, "template_name": self.template_name}

    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_learner_with_everything_filled_renders_normally(self, settings_mock, user_mock):
        settings_mock.return_value = self._course_settings(["nuts"])
        user_mock.return_value = self._user(nuts="norte_cavado")
        context = self._context()

        response = RequireProfileFieldsOnCourseAbout.run_filter(self, context, self.template_name)

        assert response == {"context": context, "template_name": self.template_name}

    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_anonymous_user_renders_normally(self, settings_mock, user_mock):
        # The about page is public, so an anonymous visitor must still see it.
        settings_mock.return_value = self._course_settings(["nuts"])
        user_mock.return_value = self._user(is_authenticated=False, nuts=None)
        context = self._context()

        response = RequireProfileFieldsOnCourseAbout.run_filter(self, context, self.template_name)

        assert response == {"context": context, "template_name": self.template_name}

    @translation.override("en")
    @override_settings(ACCOUNT_MICROFRONTEND_URL=ACCOUNT_URL)
    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_missing_field_replaces_the_page_with_the_note(self, settings_mock, user_mock):
        settings_mock.return_value = self._course_settings(["nuts", "cae4"])
        user_mock.return_value = self._user(nuts="norte_cavado", cae4=None)

        with self.assertRaises(CourseAboutRenderStarted.RenderCustomResponse) as blocked:
            RequireProfileFieldsOnCourseAbout.run_filter(self, self._context(), self.template_name)

        # The learner is told what is missing and where to go, which is the whole
        # reason this renders a response instead of redirecting.
        body = blocked.exception.response.content.decode("utf-8")
        assert "CAE4" in body
        assert f"{self.ACCOUNT_URL}?missing=cae4" in body
        # The course name is deliberately not in the copy: the learner knows which
        # course they are in, and leaving it out keeps the string translatable
        # without a placeholder.
        assert "Demo Course" not in body
        assert "please complete the following information" in body
        assert "CAE4" in blocked.exception.message

    @override_settings(ACCOUNT_MICROFRONTEND_URL="")
    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_without_an_account_url_the_page_still_renders(self, settings_mock, user_mock):
        # A note pointing nowhere would be a dead end, so the about page is left
        # alone and the enrollment filter does the blocking.
        settings_mock.return_value = self._course_settings(["nuts"])
        user_mock.return_value = self._user(nuts=None)
        context = self._context()

        response = RequireProfileFieldsOnCourseAbout.run_filter(self, context, self.template_name)

        assert response == {"context": context, "template_name": self.template_name}


class RequireProfileFieldsOnXBlockRenderTest(TestCase):
    """
    Test RequireProfileFieldsOnXBlockRender, which replaces course content with
    the profile completion panel while the learner is missing required fields.

    This is the filter that matters for a learner who is already enrolled, from
    before the course required the fields or through a bulk enrollment.
    """

    ACCOUNT_URL = "http://apps.example.com/account/"

    def setUp(self):
        super().setUp()
        self.course_key = CourseKey.from_string("course-v1:Demo+DemoX+Demo_Course")
        self.student_view_context = {}

    class FakeModel:
        """Plain stand-in, for the same reason as in the filter tests above."""

        def __init__(self, **fields):
            self.__dict__.update(fields)

    def _context(self, staff_access=False):
        return {
            "course": self.FakeModel(id=self.course_key, display_name_with_default="Demo Course"),
            "staff_access": staff_access,
        }

    def _user(self, is_authenticated=True, **extended_fields):
        return self.FakeModel(
            is_authenticated=is_authenticated,
            nau_nif=None,
            nauuserextendedmodel=self.FakeModel(**extended_fields),
            profile=self.FakeModel(),
        )

    @staticmethod
    def _course_settings(required_fields):
        return {"value": {"filter_enrollment_require_profile_fields": required_fields}}

    def _unchanged(self, context):
        return {"context": context, "student_view_context": self.student_view_context}

    @override_settings(ACCOUNT_MICROFRONTEND_URL=ACCOUNT_URL)
    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_missing_field_replaces_the_content(self, settings_mock, user_mock):
        settings_mock.return_value = self._course_settings(["nuts", "cae4"])
        user_mock.return_value = self._user(nuts="norte_cavado", cae4=None)

        with self.assertRaises(RenderXBlockStarted.RenderCustomResponse) as blocked:
            RequireProfileFieldsOnXBlockRender.run_filter(
                self, self._context(), self.student_view_context)

        # The view wraps this in a Fragment, so it has to be markup, not a response.
        assert isinstance(blocked.exception.response, str)
        assert "CAE4" in blocked.exception.response
        assert f"{self.ACCOUNT_URL}?missing=cae4" in blocked.exception.response

    @override_settings(ACCOUNT_MICROFRONTEND_URL=ACCOUNT_URL)
    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_colours_come_from_the_theme(self, settings_mock, user_mock):
        # The panel must not carry its own palette, or it drifts from the site
        # theme the moment the theme changes.
        settings_mock.return_value = self._course_settings(["nuts"])
        user_mock.return_value = self._user(nuts=None)

        with self.assertRaises(RenderXBlockStarted.RenderCustomResponse) as blocked:
            RequireProfileFieldsOnXBlockRender.run_filter(
                self, self._context(), self.student_view_context)

        markup = blocked.exception.response
        assert "btn btn-primary" in markup
        assert not re.search(r"#[0-9a-fA-F]{3,6}", markup)

    @override_settings(ACCOUNT_MICROFRONTEND_URL=ACCOUNT_URL)
    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_staff_can_always_open_the_course(self, settings_mock, user_mock):
        settings_mock.return_value = self._course_settings(["nuts"])
        user_mock.return_value = self._user(nuts=None)
        context = self._context(staff_access=True)

        response = RequireProfileFieldsOnXBlockRender.run_filter(
            self, context, self.student_view_context)

        assert response == self._unchanged(context)

    @override_settings(ACCOUNT_MICROFRONTEND_URL=ACCOUNT_URL)
    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_learner_with_everything_filled_sees_the_content(self, settings_mock, user_mock):
        settings_mock.return_value = self._course_settings(["nuts"])
        user_mock.return_value = self._user(nuts="norte_cavado")
        context = self._context()

        response = RequireProfileFieldsOnXBlockRender.run_filter(
            self, context, self.student_view_context)

        assert response == self._unchanged(context)

    @patch('nau_openedx_extensions.filters.pipeline.get_current_user')
    @patch('nau_openedx_extensions.filters.pipeline.get_other_course_settings')
    def test_course_without_the_setting_shows_the_content(self, settings_mock, user_mock):
        settings_mock.return_value = {"value": {}}
        user_mock.return_value = self._user(nuts=None)
        context = self._context()

        response = RequireProfileFieldsOnXBlockRender.run_filter(
            self, context, self.student_view_context)

        assert response == self._unchanged(context)
