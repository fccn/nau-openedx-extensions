"""
Test cases for bulk email utilities.

This module contains unit tests for the bulk email customization functions,
specifically testing the organization logo URL handling to ensure that:
- Absolute URLs (http:// or https://) are used as-is
- Relative URLs are prepended with LMS_ROOT_URL
"""
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from nau_openedx_extensions.utils.bulk_email import get_course_email_context_factory


class TestGetCourseEmailContextFactory(TestCase):
    """
    Test cases for get_course_email_context_factory function
    """

    @override_settings(LMS_ROOT_URL='https://example.com')
    @patch('organizations.api.get_course_organization')
    @patch('opaque_keys.edx.keys.CourseKey')
    def test_organization_logo_with_absolute_http_url(self, mock_course_key, mock_get_org):
        """
        Test that absolute HTTP URLs are used as-is without prepending LMS_ROOT_URL
        """
        # Setup mocks
        mock_course = Mock()
        mock_course.id = 'course-v1:Org+Course+Run'

        mock_logo = Mock()
        mock_logo.url = 'http://cdn.example.com/logos/org-logo.png'

        mock_get_org.return_value = {
            'name': 'Test Organization',
            'logo': mock_logo
        }

        # Create the wrapper function
        original_func = Mock(return_value={'course_name': 'Test Course'})
        wrapper = get_course_email_context_factory(original_func)

        # Call the wrapper
        result = wrapper(mock_course)

        # Verify the absolute URL is used as-is
        self.assertEqual(result['organization_logo'], 'http://cdn.example.com/logos/org-logo.png')
        self.assertEqual(result['organization_name'], 'Test Organization')

    @override_settings(LMS_ROOT_URL='https://example.com')
    @patch('organizations.api.get_course_organization')
    @patch('opaque_keys.edx.keys.CourseKey')
    def test_organization_logo_with_absolute_https_url(self, mock_course_key, mock_get_org):
        """
        Test that absolute HTTPS URLs are used as-is without prepending LMS_ROOT_URL
        """
        # Setup mocks
        mock_course = Mock()
        mock_course.id = 'course-v1:Org+Course+Run'

        mock_logo = Mock()
        mock_logo.url = 'https://cdn.example.com/logos/org-logo.png'

        mock_get_org.return_value = {
            'name': 'Test Organization',
            'logo': mock_logo
        }

        # Create the wrapper function
        original_func = Mock(return_value={'course_name': 'Test Course'})
        wrapper = get_course_email_context_factory(original_func)

        # Call the wrapper
        result = wrapper(mock_course)

        # Verify the absolute URL is used as-is
        self.assertEqual(result['organization_logo'], 'https://cdn.example.com/logos/org-logo.png')
        self.assertEqual(result['organization_name'], 'Test Organization')

    @override_settings(LMS_ROOT_URL='https://example.com')
    @patch('organizations.api.get_course_organization')
    @patch('opaque_keys.edx.keys.CourseKey')
    def test_organization_logo_with_relative_url(self, mock_course_key, mock_get_org):
        """
        Test that relative URLs are prepended with LMS_ROOT_URL
        """
        # Setup mocks
        mock_course = Mock()
        mock_course.id = 'course-v1:Org+Course+Run'

        mock_logo = Mock()
        mock_logo.url = '/media/organization-logos/org-logo.png'

        mock_get_org.return_value = {
            'name': 'Test Organization',
            'logo': mock_logo
        }

        # Create the wrapper function
        original_func = Mock(return_value={'course_name': 'Test Course'})
        wrapper = get_course_email_context_factory(original_func)

        # Call the wrapper
        result = wrapper(mock_course)

        # Verify LMS_ROOT_URL is prepended to relative URL
        self.assertEqual(result['organization_logo'], 'https://example.com/media/organization-logos/org-logo.png')
        self.assertEqual(result['organization_name'], 'Test Organization')

    @override_settings(LMS_ROOT_URL='https://example.com')
    @patch('organizations.api.get_course_organization')
    @patch('opaque_keys.edx.keys.CourseKey')
    def test_organization_without_logo(self, mock_course_key, mock_get_org):
        """
        Test that when organization has no logo, no organization_logo is added to context
        """
        # Setup mocks
        mock_course = Mock()
        mock_course.id = 'course-v1:Org+Course+Run'

        mock_get_org.return_value = {
            'name': 'Test Organization',
            'logo': None
        }

        # Create the wrapper function
        original_func = Mock(return_value={'course_name': 'Test Course'})
        wrapper = get_course_email_context_factory(original_func)

        # Call the wrapper
        result = wrapper(mock_course)

        # Verify no organization_logo is in context
        self.assertNotIn('organization_logo', result)
        self.assertEqual(result['organization_name'], 'Test Organization')

    @override_settings(LMS_ROOT_URL='https://example.com')
    @patch('organizations.api.get_course_organization')
    @patch('opaque_keys.edx.keys.CourseKey')
    def test_no_organization(self, mock_course_key, mock_get_org):
        """
        Test that when no organization is found, original context is returned
        """
        # Setup mocks
        mock_course = Mock()
        mock_course.id = 'course-v1:Org+Course+Run'

        mock_get_org.return_value = None

        # Create the wrapper function
        original_context = {'course_name': 'Test Course'}
        original_func = Mock(return_value=original_context)
        wrapper = get_course_email_context_factory(original_func)

        # Call the wrapper
        result = wrapper(mock_course)

        # Verify original context is returned without modifications
        self.assertNotIn('organization_logo', result)
        self.assertNotIn('organization_name', result)
        self.assertEqual(result['course_name'], 'Test Course')

    @override_settings(LMS_ROOT_URL='https://example.com')
    @patch('organizations.api.get_course_organization')
    @patch('opaque_keys.edx.keys.CourseKey')
    def test_exception_handling(self, mock_course_key, mock_get_org):
        """
        Test that exceptions are caught and original context is returned
        """
        # Setup mocks to raise an exception
        mock_course = Mock()
        mock_course.id = 'course-v1:Org+Course+Run'

        mock_get_org.side_effect = Exception("Database error")

        # Create the wrapper function
        original_context = {'course_name': 'Test Course'}
        original_func = Mock(return_value=original_context)
        wrapper = get_course_email_context_factory(original_func)

        # Call the wrapper - should not raise exception
        result = wrapper(mock_course)

        # Verify original context is returned
        self.assertEqual(result, original_context)
