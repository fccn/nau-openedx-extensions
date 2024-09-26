"""
Tests for certificates context overrides.
"""
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from django.test import TestCase
from nau_openedx_extensions.certificates.context_overrides import CertificatesContextCohortOverride


class CertificatesContextOverridesTest(TestCase):
    """
    Test certificates context overrides for cohorts.
    The override configuration is managed on the <CMS_HOST>/settings/advanced/<course_id>
    on field name `cert_html_view_overrides`.
    """

    @patch('nau_openedx_extensions.certificates.context_overrides.get_cohort')
    def test_certificates_context_overrides_no_cohort_and_no_override(self, get_cohort_mock):
        """
        Check if no cohort and no override.
        """
        get_cohort_mock.return_value = None

        context = {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
        }
        result = CertificatesContextCohortOverride.run_filter(None, context, "some_template")
        get_cohort_mock.assert_not_called()
        
        self.assertDictEqual(result['context'], {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
        })

    @patch('nau_openedx_extensions.certificates.context_overrides.get_cohort')
    def test_certificates_context_overrides_with_cohort_no_override(self, get_cohort_mock):
        """
        Check that no override is applied when the learner has a cohort but no override is configured.
        """
        mocked_cohort = MagicMock()
        cohort_name_property = PropertyMock(return_value="SomeGroup")
        type(mocked_cohort).name = cohort_name_property
        get_cohort_mock.return_value = mocked_cohort

        context = {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
        }
        CertificatesContextCohortOverride.run_filter(None, context, "some_template")
        get_cohort_mock.assert_not_called()

    @patch('nau_openedx_extensions.certificates.context_overrides.get_cohort')
    def test_certificates_context_overrides_with_no_cohort_and_with_override(self, get_cohort_mock):
        """
        Check that no override is applied when the learner hasn't a cohort and the course has an override.
        """
        get_cohort_mock.return_value = None

        context = {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
            "footer_additional_logo": "http://lms.example.com/base_logo.png",
            "cohort_overrides" : {
                "SomeGroup": {
                    "footer_additional_logo": "http://lms.example.com/override_logo.png",
                },
            },
        }
        result = CertificatesContextCohortOverride.run_filter(None, context, "some_template")
        get_cohort_mock.assert_called_once_with("nau@example.com", "course-v1:Demo+DemoX+Demo_Course")

        self.assertDictEqual(result['context'], {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
            "footer_additional_logo": "http://lms.example.com/base_logo.png",
            "cohort_overrides" : {
                "SomeGroup": {
                    "footer_additional_logo": "http://lms.example.com/override_logo.png",
                },
            },
        })


    @patch('nau_openedx_extensions.certificates.context_overrides.get_cohort')
    def test_certificates_context_overrides_with_cohort_and_override_dont_match(self, get_cohort_mock):
        """
        Check that the override isn't being applied when the learner belongs to a cohort that isn't configured on the override.
        """
        mocked_cohort = MagicMock()
        cohort_name_property = PropertyMock(return_value="some_group_not_configured_on_override")
        type(mocked_cohort).name = cohort_name_property
        get_cohort_mock.return_value = mocked_cohort

        context = {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
            "footer_additional_logo": "http://lms.example.com/base_logo.png",
            "cohort_overrides" : {
                "SomeGroup": {
                    "footer_additional_logo": "http://lms.example.com/override_logo.png",
                },
            },
        }
        result = CertificatesContextCohortOverride.run_filter(None, context, "some_template")
        get_cohort_mock.assert_called_once_with("nau@example.com", "course-v1:Demo+DemoX+Demo_Course")

        self.assertDictEqual(result['context'], {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
            "footer_additional_logo": "http://lms.example.com/base_logo.png",
            "cohort_overrides" : {
                "SomeGroup": {
                    "footer_additional_logo": "http://lms.example.com/override_logo.png",
                },
            },
        })

    @patch('nau_openedx_extensions.certificates.context_overrides.get_cohort')
    def test_certificates_context_overrides_with_cohort_and_override(self, get_cohort_mock):
        """
        Check that the override is being applied if the learner belongs to a cohort and that cohort is configured has override.
        """
        mocked_cohort = MagicMock()
        cohort_name_property = PropertyMock(return_value="SomeGroup")
        type(mocked_cohort).name = cohort_name_property
        get_cohort_mock.return_value = mocked_cohort

        context = {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
            "footer_additional_logo": "http://lms.example.com/base_logo.png",
            "cohort_overrides" : {
                "SomeGroup": {
                    "footer_additional_logo": "http://lms.example.com/override_logo.png",
                },
            },
        }
        result = CertificatesContextCohortOverride.run_filter(None, context, "some_template")
        get_cohort_mock.assert_called_once_with("nau@example.com", "course-v1:Demo+DemoX+Demo_Course")

        self.assertDictEqual(result['context'], {
            "username": "nau@example.com",
            "course_id": "course-v1:Demo+DemoX+Demo_Course",
            "footer_additional_logo": "http://lms.example.com/override_logo.png",
            "cohort_overrides" : {
                "SomeGroup": {
                    "footer_additional_logo": "http://lms.example.com/override_logo.png",
                },
            },
        })
