"""
Tests for certificate filters module.
"""

from unittest.mock import MagicMock, Mock, patch

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.test import TestCase
from django.test.utils import override_settings
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.filters.filter_certificates import FilterUpdateCertificateContext

FILTERS_PATH = "nau_openedx_extensions.filters.filter_certificates"


# pylint: disable=protected-access
class FilterUpdateCertificateContextTest(TestCase):
    """
    Test the FilterUpdateCertificateContext that enhances certificate context with user profile data,
    course grades, and custom interpolated strings.
    """

    patch_get_course = patch(f"{FILTERS_PATH}.get_course")
    patch_get_request = patch(f"{FILTERS_PATH}.get_current_request")
    patch_cert_config = patch(f"{FILTERS_PATH}.CertificateHtmlViewConfiguration")
    patch_translation = patch(f"{FILTERS_PATH}.translation")
    patch_get_catalog_data = patch(f"{FILTERS_PATH}.get_catalog_data_for_course")
    patch_get_custom_template = patch(f"{FILTERS_PATH}.get_custom_template_and_language")
    patch_get_course_grades = patch(f"{FILTERS_PATH}.get_course_grades")
    patch_log = patch(f"{FILTERS_PATH}.log")

    def setUp(self):
        """Set up test fixtures."""
        self.filter = FilterUpdateCertificateContext(filter_type=Mock(), running_pipeline=Mock())
        self.course_id_str = "course-v1:Demo+DemoX+Demo_Course"
        self.course_key = CourseKey.from_string(self.course_id_str)
        self.user = MagicMock(username="testuser", email="test@example.com")
        self.request_user = MagicMock(username="testuser2", email="test2@example.com")
        self.course = MagicMock(id=self.course_key, display_name="Test Course")
        self.user_certificate = MagicMock(grade="85", mode="verified", user=self.user)
        self.context = {"course_id": self.course_id_str, "user_certificate": self.user_certificate}
        self.request = MagicMock(user=self.request_user)

    @patch_cert_config
    @patch_get_course
    def test_get_properties_basic(
        self,
        mock_get_course: Mock,
        mock_cert_config: Mock,
    ):
        with patch.object(self.filter, "_determine_certificate_language") as mock_determine_lang:
            self.course.cert_html_view_overrides = {"nau_certs_settings": {"setting": "value"}}
            mock_get_course.return_value = self.course
            mock_cert_config.get_config.return_value = {"config": "test"}
            mock_determine_lang.return_value = "en"

            result = self.filter._get_properties(self.context, None)

            self.assertEqual(result["certificate_language"], "en")
            self.assertEqual(result["configuration"], {"config": "test"})
            self.assertEqual(result["course"], self.course)
            self.assertEqual(result["course_key"], self.course_key)
            self.assertEqual(result["nau_cert_settings"], {"setting": "value"})
            self.assertEqual(result["user"], self.user)
            self.assertEqual(result["user_certificate"], self.user_certificate)

    @patch_translation
    def test_determine_certificate_language_no_custom_template(self, mock_translation: Mock):
        """
        Test _determine_certificate_language with no custom template.
        """
        mock_translation.get_language.return_value = "pt-br"

        result = self.filter._determine_certificate_language(self.course, self.user_certificate, None)

        self.assertEqual(result, "pt-br")

    @patch_translation
    @patch_get_catalog_data
    @patch_get_custom_template
    def test_determine_certificate_language_with_custom_template(
        self, mock_get_custom_template: Mock, mock_get_catalog_data: Mock, mock_translation: Mock
    ):
        """
        Test _determine_certificate_language with custom template.
        """
        mock_translation.get_language.return_value = "en"
        mock_get_catalog_data.return_value = {"content_language": "pt-pt"}
        mock_get_custom_template.return_value = (None, "pt-pt")

        result = self.filter._determine_certificate_language(self.course, self.user_certificate, "custom_template")

        self.assertEqual(result, "pt-pt")

    @patch_translation
    @patch_get_catalog_data
    @patch_get_custom_template
    def test_determine_certificate_language_custom_template_no_language(
        self, mock_get_custom_template: Mock, mock_get_catalog_data: Mock, mock_translation: Mock
    ):
        """
        Test _determine_certificate_language with custom template but no custom language.
        """
        mock_translation.get_language.return_value = "en"
        mock_get_catalog_data.return_value = {"content_language": "pt-pt"}
        mock_get_custom_template.return_value = (None, None)

        result = self.filter._determine_certificate_language(self.course, self.user_certificate, "custom_template")

        self.assertEqual(result, "en")

    def test_update_context_with_custom_form_existing_model(self):
        """
        Test _update_context_with_custom_form with existing model instance.
        """
        # Create mock custom model with fields
        mock_model_class = MagicMock()
        mock_instance = MagicMock()
        mock_model_class.objects.get.return_value = mock_instance
        # Mock model fields
        boolean_field = MagicMock(spec=models.BooleanField)
        boolean_field.name = "allow_newsletter"
        char_field = MagicMock(spec=models.CharField)
        char_field.name = "nif"
        text_field = MagicMock(spec=models.TextField)
        text_field.name = "bio"
        integer_field = MagicMock(spec=models.IntegerField)
        integer_field.name = "age"
        mock_instance._meta.fields = [boolean_field, char_field, text_field, integer_field]
        mock_instance.allow_newsletter = True
        mock_instance.nif = "123456789"
        mock_instance.bio = "Test bio"
        mock_instance.age = 25
        context = {}

        self.filter._update_context_with_custom_form(self.user, mock_model_class, context)

        self.assertEqual(context["allow_newsletter"], True)
        self.assertEqual(context["nif"], "123456789")
        self.assertEqual(context["bio"], "Test bio")
        self.assertNotIn("age", context)

    def test_update_context_with_custom_form_no_model(self):
        """
        Test _update_context_with_custom_form with no existing model instance.
        """
        mock_model_class = MagicMock()
        mock_model_class.objects.get.side_effect = ObjectDoesNotExist()
        # Mock empty instance
        mock_empty_instance = MagicMock()
        mock_model_class.return_value = mock_empty_instance
        # Mock model fields
        boolean_field = MagicMock(spec=models.BooleanField)
        boolean_field.name = "allow_newsletter"
        mock_empty_instance._meta.fields = [boolean_field]
        mock_empty_instance.allow_newsletter = None
        context = {}

        self.filter._update_context_with_custom_form(self.user, mock_model_class, context)

        self.assertEqual(context["allow_newsletter"], None)

    @patch_get_course_grades
    def test_update_context_with_grades_basic(self, mock_get_course_grades: Mock):
        """
        Test _update_context_with_grades basic functionality.
        """
        context = {}
        nau_certs_settings = {"calculate_grades_context": False}

        self.filter._update_context_with_grades(
            self.user, self.course, context, nau_certs_settings, self.user_certificate, "en"
        )

        self.assertEqual(context["certificate_final_grade"], "85")
        mock_get_course_grades.assert_not_called()

    @patch_get_course_grades
    def test_update_context_with_grades_with_calculation(self, mock_get_course_grades: Mock):
        """
        Test _update_context_with_grades with grades calculation enabled.
        """
        # Mock grades object
        mock_grades = MagicMock()
        mock_grades.percent = 0.85
        mock_grades.letter_grade = "B"
        mock_grades.passed = True
        mock_get_course_grades.return_value = mock_grades
        context = {}
        nau_certs_settings = {"calculate_grades_context": True}

        self.filter._update_context_with_grades(
            self.user, self.course, context, nau_certs_settings, self.user_certificate, "en"
        )

        self.assertEqual(context["certificate_final_grade"], "85")
        self.assertEqual(context["course_letter_grade"], "B")
        self.assertEqual(context["user_has_approved_course"], True)
        self.assertEqual(context["course_percent_grade"], 0.85)
        self.assertEqual(context["course_grade_scale_10"], 8.5)
        self.assertEqual(context["course_grade_scale_20"], 17.0)

    @patch_get_course_grades
    @patch_log
    def test_update_context_with_grades_exception_handling(self, mock_log: Mock, mock_get_course_grades: Mock):
        """
        Test _update_context_with_grades exception handling.
        """
        mock_get_course_grades.side_effect = Exception("Grades error")
        context = {}
        nau_certs_settings = {"calculate_grades_context": True}

        self.filter._update_context_with_grades(
            self.user, self.course, context, nau_certs_settings, self.user_certificate, "en"
        )

        self.assertEqual(context["certificate_final_grade"], "85")
        mock_log.error.assert_called_once()

    @patch_get_course_grades
    def test_update_context_with_grades_with_qualitative_grade(self, mock_get_course_grades: Mock):
        """
        Test _update_context_with_grades with qualitative grade configuration.
        """
        mock_grades = MagicMock()
        mock_grades.percent = 0.85
        mock_grades.letter_grade = "B"
        mock_grades.passed = True
        mock_get_course_grades.return_value = mock_grades
        context = {}
        nau_certs_settings = {
            "calculate_grades_context": True,
            "course_qualitative_grade": {
                "ranges": [{"grade_text": {"en": "Excellent"}, "min_included": 80, "max_excluded": 101}],
                "grade_round_format": "course_percent_grade:.0%",
            },
        }

        with patch.object(self.filter, "_course_qualitative_grade") as mock_qualitative:
            self.filter._update_context_with_grades(
                self.user, self.course, context, nau_certs_settings, self.user_certificate, "en"
            )

            mock_qualitative.assert_called_once()

    def test_course_qualitative_grade_basic(self):
        """
        Test _course_qualitative_grade basic functionality.
        """
        context = {"course_percent_grade": 0.85}
        course_qualitative_grade_config = {
            "ranges": [{"grade_text": {"en": "Excellent"}, "min_included": 80, "max_excluded": 101}],
            "grade_round_format": "course_percent_grade:.0%",
        }

        self.filter._course_qualitative_grade(self.user, self.course, context, course_qualitative_grade_config, "en")

        self.assertEqual(context["course_grade_rounded"], "85")
        self.assertEqual(context["course_grade_qualitative"], "Excellent")

    @patch_log
    def test_course_qualitative_grade_format_error(self, mock_log: Mock):
        """
        Test _course_qualitative_grade with format error.
        """
        context = {"invalid_key": 0.85}  # Missing course_percent_grade
        course_qualitative_grade_config = {"grade_round_format": "course_percent_grade:.0%"}

        self.filter._course_qualitative_grade(self.user, self.course, context, course_qualitative_grade_config, "en")

        mock_log.error.assert_called_once()
        self.assertEqual(context["course_grade_rounded"], "0")

    def test_format_grade_portuguese(self):
        """
        Test _format_grade with Portuguese language.
        """
        result = self.filter._format_grade("85.5", "pt-pt")
        self.assertEqual(result, "85,5")

        result = self.filter._format_grade("90.0", "pt")
        self.assertEqual(result, "90,0")

    def test_format_grade_english(self):
        """
        Test _format_grade with English language.
        """
        result = self.filter._format_grade("85.5", "en")
        self.assertEqual(result, "85.5")

        result = self.filter._format_grade("90.0", "fr")
        self.assertEqual(result, "90.0")

    @override_settings(LANGUAGE_CODE="en")
    def test_get_qualitative_grade_string_grade_text(self):
        """
        Test _get_qualitative_grade with string grade text.
        """
        ranges = [{"grade_text": "Excellent", "min_included": 80, "max_excluded": 101}]

        result = self.filter._get_qualitative_grade(self.user, self.course, "en", ranges, "85")

        self.assertEqual(result, "Excellent")

    @override_settings(LANGUAGE_CODE="en")
    def test_get_qualitative_grade_dict_grade_text(self):
        """
        Test _get_qualitative_grade with dictionary grade text.
        """
        ranges = [{"grade_text": {"en": "Excellent", "pt-pt": "Excelente"}, "min_included": 80, "max_excluded": 101}]

        result = self.filter._get_qualitative_grade(self.user, self.course, "en", ranges, "85")

        self.assertEqual(result, "Excellent")

    @override_settings(LANGUAGE_CODE="en")
    def test_get_qualitative_grade_dict_grade_text_fallback_to_default(self):
        """
        Test _get_qualitative_grade with dictionary grade text fallback to default language.
        """
        ranges = [{"grade_text": {"en": "Excellent", "pt-pt": "Excelente"}, "min_included": 80, "max_excluded": 101}]

        result = self.filter._get_qualitative_grade(
            self.user,
            self.course,
            "fr",
            ranges,
            "85",  # French not available
        )

        self.assertEqual(result, "Excellent")  # Should fallback to English (LANGUAGE_CODE)

    @patch_log
    def test_get_qualitative_grade_no_matching_range(self, mock_log: Mock):
        """
        Test _get_qualitative_grade with no matching range.
        """
        ranges = [{"grade_text": "Excellent", "min_included": 80, "max_excluded": 101}]

        result = self.filter._get_qualitative_grade(
            self.user,
            self.course,
            "en",
            ranges,
            "50",  # Below range
        )

        self.assertIsNone(result)
        mock_log.warning.assert_called_once()

    @patch_log
    def test_get_qualitative_grade_invalid_grade(self, mock_log: Mock):
        """
        Test _get_qualitative_grade with invalid grade format.
        """
        ranges = [{"grade_text": "Excellent", "min_included": 80, "max_excluded": 101}]

        result = self.filter._get_qualitative_grade(self.user, self.course, "en", ranges, "invalid")

        self.assertIsNone(result)
        mock_log.exception.assert_called_once()

    def test_update_context_with_interpolated_strings_basic(self):
        """
        Test _update_context_with_interpolated_strings basic functionality.
        """
        context = {"course_grade": "85"}
        nau_cert_settings = {
            "interpolated_strings": {"accomplishment_copy_course_description": {"en": "Your grade is {course_grade}"}}
        }

        self.filter._update_context_with_interpolated_strings(context, nau_cert_settings, "en")

        self.assertEqual(context["accomplishment_copy_course_description"], "Your grade is 85")

    @patch_log
    def test_update_context_with_interpolated_strings_format_error(self, mock_log: Mock):
        """
        Test _update_context_with_interpolated_strings with formatting error.
        """
        context = {"course_grade": "85"}
        nau_cert_settings = {
            "interpolated_strings": {
                "accomplishment_copy_course_description": {
                    "en": "Your grade is {missing_key}"  # Missing key
                }
            }
        }

        self.filter._update_context_with_interpolated_strings(context, nau_cert_settings, "en")

        self.assertNotIn("accomplishment_copy_course_description", context)
        mock_log.error.assert_called_once()

    def test_get_interpolated_strings_basic(self):
        """
        Test _get_interpolated_strings basic functionality.
        """
        nau_cert_settings = {
            "interpolated_strings": {
                "accomplishment_copy_course_description": {"en": "English text", "pt-pt": "Portuguese text"},
                "another_string": {"en": "Another English text", "pt-pt": "Another Portuguese text"},
            }
        }

        result = self.filter._get_interpolated_strings(nau_cert_settings, "en")

        expected = {"accomplishment_copy_course_description": "English text", "another_string": "Another English text"}
        self.assertEqual(result, expected)

    def test_get_interpolated_strings_partial_match(self):
        """
        Test _get_interpolated_strings with partial language match.
        """
        nau_cert_settings = {
            "interpolated_strings": {
                "accomplishment_copy_course_description": {"en": "English text", "pt": "Portuguese text"}
            }
        }

        result = self.filter._get_interpolated_strings(nau_cert_settings, "pt-pt")

        expected = {"accomplishment_copy_course_description": "Portuguese text"}
        self.assertEqual(result, expected)

    def test_get_interpolated_strings_no_matching_language(self):
        """
        Test _get_interpolated_strings with no matching language.
        """
        nau_cert_settings = {
            "interpolated_strings": {
                "accomplishment_copy_course_description": {"en": "English text", "pt-pt": "Portuguese text"}
            }
        }

        result = self.filter._get_interpolated_strings(nau_cert_settings, "fr")

        self.assertEqual(result, {})

    def test_get_interpolated_strings_no_interpolated_strings(self):
        """
        Test _get_interpolated_strings with no interpolated strings configuration.
        """
        nau_cert_settings = {}

        result = self.filter._get_interpolated_strings(nau_cert_settings, "en")

        self.assertEqual(result, {})

    @patch_log
    def test_get_interpolated_strings_attribute_error(self, mock_log: Mock):
        """
        Test _get_interpolated_strings with AttributeError handling.
        """
        nau_cert_settings = {"interpolated_strings": {"accomplishment_copy_course_description": "not_a_dict"}}

        result = self.filter._get_interpolated_strings(nau_cert_settings, "en")

        mock_log.error.assert_called_once()
        self.assertEqual(result, {})

    @patch_get_request
    @patch_cert_config
    @patch_get_course
    def test_get_properties_preview_certificate(
        self,
        mock_get_course: Mock,
        mock_cert_config: Mock,
        mock_get_request: Mock,
    ):
        """
        Test _get_properties for preview certificate, current logged-in user is different from certificate user.
        """
        # Simulate preview certificate that is not saved/linked to user
        self.user_certificate.user = None
        with patch.object(self.filter, "_determine_certificate_language") as mock_determine_lang:
            self.course.cert_html_view_overrides = {"nau_certs_settings": {"setting": "value"}}
            mock_get_course.return_value = self.course
            mock_cert_config.get_config.return_value = {"config": "test"}
            mock_determine_lang.return_value = "en"
            mock_get_request.return_value = self.request

            result = self.filter._get_properties(self.context, None)

            self.assertEqual(result["certificate_language"], "en")
            self.assertEqual(result["configuration"], {"config": "test"})
            self.assertEqual(result["course"], self.course)
            self.assertEqual(result["course_key"], self.course_key)
            self.assertEqual(result["nau_cert_settings"], {"setting": "value"})
            self.assertEqual(result["user"], self.request_user)
            self.assertEqual(result["user_certificate"], self.user_certificate)
