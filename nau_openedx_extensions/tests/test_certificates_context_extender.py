"""
Tests for the pipeline module used in nau_openex_extensions
"""

from unittest.mock import MagicMock

from django.test import TestCase

from nau_openedx_extensions.certificates.context_extender import (
    get_qualitative_grade,
    update_context_with_interpolated_strings,
)


class CertificatesContextExtenderTest(TestCase):
    """Test the certificates context extender."""

    def test_get_qualitative_grade_basic_percentage(self):
        """
        Test the `get_qualitative_grade` method using a percentage distribution of the grades.
        """
        user = MagicMock(email="example@example.com", username="example")
        course = MagicMock(display_name="Learn something about some subject")
        ranges = \
            [
                {
                    "grade_text": "Insuficient",
                    "min_included": 0,
                    "max_excluded": 50
                },
                {
                    "grade_text": {
                        "pt-pt": "Regular",
                        "en": "Regular"
                    },
                    "min_included": 50,
                    "max_excluded": 65
                },
                {
                    "grade_text": {
                        "pt-pt": "Bom",
                        "en": "Good"
                    },
                    "min_included": 65,
                    "max_excluded": 80
                },
                {
                    "grade_text": {
                        "pt-pt": "Muito Bom",
                        "en": "Very Good"
                    },
                    "min_included": 80,
                    "max_excluded": 90
                },
                {
                    "grade_text": {
                        "pt-pt": "Excelente",
                        "en": "Excelent"
                    },
                    "min_included": 90,
                    "max_excluded": 101
                }
            ]

        self.assertEqual("Regular", get_qualitative_grade(user, course,  "pt-pt", ranges, "51"))
        self.assertEqual("Muito Bom", get_qualitative_grade(user, course,  "pt-pt", ranges, "80"))
        self.assertEqual("Very Good", get_qualitative_grade(user, course,  "en", ranges, "80.999"))
        self.assertEqual("Insuficient", get_qualitative_grade(user, course,  "en", ranges, "49"))
        self.assertEqual("Insuficient", get_qualitative_grade(user, course,  "pt-pt", ranges, "0"))

    def test_update_context_with_interpolated_strings(self):
        """
        Test update certificate context with custom qualitative grade.
        """
        nau_certs_settings = {
            "interpolated_strings": {
                "accomplishment_copy_course_description": {
                    "pt-pt": ", com nota de numérica de {course_percent_grade:.0%} \
numa escala de 0 a 10 e nota qualitativa de {course_grade_qualitative}.",
                    "en": ", with a numberic grade of {course_percent_grade:.0%} \
on scale from 0 to 10 and a qualitative grade of {course_grade_qualitative}."
                }
            }
        }
        context = {
            "course_grade_qualitative": "54.1",
            "course_percent_grade": 0.521
        }

        expected_context = {
            'course_grade_qualitative': '54.1',
            'course_percent_grade': 0.521,
            'accomplishment_copy_course_description':
            ', com nota de numérica de 52% numa escala de 0 a 10 e nota qualitativa de 54.1.'
        }
        update_context_with_interpolated_strings(context, nau_certs_settings, "pt-pt")
        print(context)
        self.assertDictEqual(expected_context, context)
