"""
Tests the separation layer between edxapp and the plugin
"""
from django.test import TestCase
from django.conf import settings
from unittest.mock import Mock, patch

from nau_openedx_extensions.edxapp_wrapper import course_module


class CourseMetadataTest(TestCase):
    """Test"""

    @patch('nau_openedx_extensions.edxapp_wrapper.course_module.import_module')
    def test_imported_module_is_used(self, import_mock):
        """
        Testing the backend is imported and used
        """
        import_mock.return_value = Mock()
        backend = import_mock

        course_module.get_other_course_settings()

        import_mock.assert_called_once_with(settings.NAU_COURSE_MODULE)
        backend.assert_called_once()
