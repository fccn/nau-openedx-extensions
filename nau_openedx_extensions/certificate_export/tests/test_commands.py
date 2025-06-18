"""
Unit tests for certificate export commands.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management.base import CommandError, OutputWrapper
from django.test import TestCase, override_settings
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.certificate_export.management.commands.export_course_certificates_pdfs import (
    DEFAULTS,
    Command,
    get_setting,
)


class GetSettingTest(TestCase):
    """Test the get_setting function."""

    def test_get_setting_with_existing_setting(self):
        """Test getting a setting that exists in Django settings."""
        with override_settings(NAU_CERTIFICATE_BATCH_SIZE=200):
            result = get_setting("NAU_CERTIFICATE_BATCH_SIZE")
            self.assertEqual(result, 200)

    def test_get_setting_with_default_value(self):
        """Test getting a setting that doesn't exist, should return default."""
        setting_name = "NAU_CERTIFICATE_BATCH_SIZE"
        if hasattr(settings, setting_name):
            delattr(settings, setting_name)

        result = get_setting("NAU_CERTIFICATE_BATCH_SIZE")
        self.assertEqual(result, DEFAULTS["NAU_CERTIFICATE_BATCH_SIZE"])

    def test_get_setting_with_nonexistent_default(self):
        """Test getting a setting that doesn't exist and has no default."""
        result = get_setting("NONEXISTENT_SETTING")
        self.assertIsNone(result)


class ExportCourseCertificatesPdfsCommandTest(TestCase):
    """Test cases for the export_course_certificates_pdfs command."""

    patch_export_course_certificates_to_zip = patch(
        "nau_openedx_extensions.certificate_export.management.commands"
        ".export_course_certificates_pdfs.export_course_certificates_to_zip"
    )
    patch_generated_certificate = patch(
        "nau_openedx_extensions.certificate_export."
        "management.commands.export_course_certificates_pdfs.GeneratedCertificate"
    )

    def setUp(self):
        """Set up test data."""
        super().setUpClass()
        self.valid_course_id = "course-v1:NAU+Demo+DemoCourse"
        self.valid_course_key = CourseKey.from_string(self.valid_course_id)
        self.valid_download_url = "https://example.com/certificates"
        self.command = Command()
        self.command.stdout = OutputWrapper(StringIO())

    @patch_export_course_certificates_to_zip
    @patch_generated_certificate
    def test_successful_export_single_course(self, mock_generated_certificate, mock_export_task):
        """Test successful export for a single course."""
        mock_certificates = MagicMock()
        mock_certificates.values_list.return_value = ["uuid1", "uuid2", "uuid3"]
        mock_generated_certificate.objects.filter.return_value = mock_certificates
        mock_export_task.delay.return_value = None

        with override_settings(NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url):
            options = {
                "course_ids": [self.valid_course_id],
                "certificate_download_url": self.valid_download_url,
            }
            self.command.set_arguments(options)
            self.command.export_pdfs()

        mock_export_task.delay.assert_called_once_with(
            self.valid_course_id,
            ["uuid1", "uuid2", "uuid3"],
            self.valid_download_url,
            DEFAULTS["NAU_CERTIFICATE_TEMP_FOLDER"],
            DEFAULTS["NAU_CERTIFICATE_BATCH_SIZE"],
            DEFAULTS["NAU_CERTIFICATE_DOWNLOAD_TIMEOUT"],
            DEFAULTS["NAU_CERTIFICATE_MAX_WORKERS"],
        )

        output = self.command.stdout.getvalue()
        self.assertIn(f"Dispatching export task for course {self.valid_course_id} with 3 certificates...", output)
        self.assertIn(f"Task dispatched successfully for course {self.valid_course_id}", output)

    @patch_export_course_certificates_to_zip
    @patch_generated_certificate
    def test_successful_export_multiple_courses(self, mock_generated_certificate, mock_export_task):
        """Test successful export for multiple courses."""
        course_id_1 = "course-v1:NAU+Demo+Course1"
        course_id_2 = "course-v1:NAU+Demo+Course2"
        mock_certificates_1 = MagicMock()
        mock_certificates_1.values_list.return_value = ["uuid1", "uuid2"]
        mock_certificates_2 = MagicMock()
        mock_certificates_2.values_list.return_value = ["uuid3", "uuid4", "uuid5"]

        def mock_filter(course_id):
            if course_id == CourseKey.from_string(course_id_1):
                return mock_certificates_1
            elif course_id == CourseKey.from_string(course_id_2):
                return mock_certificates_2
            return MagicMock()

        mock_generated_certificate.objects.filter.side_effect = mock_filter
        mock_export_task.delay.return_value = None

        with override_settings(NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url):
            options = {
                "course_ids": [course_id_1, course_id_2],
                "certificate_download_url": self.valid_download_url,
            }
            self.command.set_arguments(options)
            self.command.export_pdfs()

        self.assertEqual(mock_export_task.delay.call_count, 2)

        output = self.command.stdout.getvalue()
        self.assertIn("Task dispatched successfully for course course-v1:NAU+Demo+Course1", output)
        self.assertIn("Task dispatched successfully for course course-v1:NAU+Demo+Course2", output)

    @patch_generated_certificate
    def test_no_certificates_found(self, mock_generated_certificate):
        """Test when no certificates are found for a course."""
        mock_certificates = MagicMock()
        mock_certificates.values_list.return_value = []
        mock_generated_certificate.objects.filter.return_value = mock_certificates

        with override_settings(NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url):
            options = {
                "course_ids": [self.valid_course_id],
                "certificate_download_url": self.valid_download_url,
            }
            self.command.set_arguments(options)
            self.command.export_pdfs()

        output = self.command.stdout.getvalue()
        self.assertIn(f"No certificates found for course {self.valid_course_id}", output)

    def test_invalid_course_id(self):
        """Test with invalid course ID."""
        invalid_course_id = "invalid-course-id"

        with override_settings(NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url):
            options = {
                "course_ids": [invalid_course_id],
                "certificate_download_url": self.valid_download_url,
            }
            self.command.set_arguments(options)
            self.command.export_pdfs()

        output = self.command.stdout.getvalue()
        self.assertIn(f"Invalid course ID: {invalid_course_id}", output)

    def test_missing_certificate_download_url(self):
        """Test when certificate_download_url is not provided."""
        options = {
            "course_ids": [self.valid_course_id],
        }
        with self.assertRaises(CommandError) as context:
            self.command.set_arguments(options)

        self.assertIn("certificate_download_url is required", str(context.exception))

    def test_invalid_certificate_download_url(self):
        """Test with invalid certificate_download_url."""
        invalid_url = "not-a-valid-url"

        options = {
            "course_ids": [self.valid_course_id],
            "certificate_download_url": invalid_url,
        }
        with self.assertRaises(CommandError) as context:
            self.command.set_arguments(options)

        self.assertIn("Invalid certificate_download_url format", str(context.exception))

    def test_invalid_batch_size(self):
        """Test with invalid batch size."""
        options = {
            "course_ids": [self.valid_course_id],
            "certificate_download_url": self.valid_download_url,
            "batch_size": -1,
        }
        with self.assertRaises(CommandError) as context:
            self.command.set_arguments(options)

        self.assertIn("batch_size must be greater than 0", str(context.exception))

    def test_invalid_download_timeout(self):
        """Test with invalid download timeout."""
        options = {
            "course_ids": [self.valid_course_id],
            "certificate_download_url": self.valid_download_url,
            "download_timeout": -1,
        }
        with self.assertRaises(CommandError) as context:
            self.command.set_arguments(options)

        self.assertIn("download_timeout must be greater than 0", str(context.exception))

    def test_invalid_max_workers(self):
        """Test with invalid max workers."""
        options = {
            "course_ids": [self.valid_course_id],
            "certificate_download_url": self.valid_download_url,
            "max_workers": -1,
        }
        with self.assertRaises(CommandError) as context:
            self.command.set_arguments(options)

        self.assertIn("max_workers must be greater than 0", str(context.exception))

    def test_command_line_arguments_override_settings(self):
        """Test that command line arguments override Django settings."""
        custom_batch_size = 50
        custom_timeout = 120
        custom_workers = 4
        custom_temp_folder = "/custom/temp/folder"

        with override_settings(
            NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url,
            NAU_CERTIFICATE_BATCH_SIZE=100,
            NAU_CERTIFICATE_DOWNLOAD_TIMEOUT=60,
            NAU_CERTIFICATE_MAX_WORKERS=8,
            NAU_CERTIFICATE_TEMP_FOLDER="/default/temp/folder",
        ):
            options = {
                "course_ids": [self.valid_course_id],
                "certificate_download_url": self.valid_download_url,
                "batch_size": custom_batch_size,
                "download_timeout": custom_timeout,
                "max_workers": custom_workers,
                "certificate_temp_folder": custom_temp_folder,
            }

            self.command.set_arguments(options)

            self.assertEqual(self.command.batch_size, custom_batch_size)
            self.assertEqual(self.command.download_timeout, custom_timeout)
            self.assertEqual(self.command.max_workers, custom_workers)
            self.assertEqual(self.command.certificate_temp_folder, custom_temp_folder)

    def test_settings_override_defaults(self):
        """Test that Django settings override default values."""
        custom_batch_size = 75
        custom_timeout = 90
        custom_workers = 6
        custom_temp_folder = "/settings/temp/folder"

        with override_settings(
            NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url,
            NAU_CERTIFICATE_BATCH_SIZE=custom_batch_size,
            NAU_CERTIFICATE_DOWNLOAD_TIMEOUT=custom_timeout,
            NAU_CERTIFICATE_MAX_WORKERS=custom_workers,
            NAU_CERTIFICATE_TEMP_FOLDER=custom_temp_folder,
        ):
            options = {
                "course_ids": [self.valid_course_id],
                "certificate_download_url": self.valid_download_url,
            }

            self.command.set_arguments(options)

            self.assertEqual(self.command.batch_size, custom_batch_size)
            self.assertEqual(self.command.download_timeout, custom_timeout)
            self.assertEqual(self.command.max_workers, custom_workers)
            self.assertEqual(self.command.certificate_temp_folder, custom_temp_folder)

    def test_defaults_used_when_no_settings(self):
        """Test that default values are used when no settings are provided."""
        for setting_name in DEFAULTS:
            if hasattr(settings, setting_name):
                delattr(settings, setting_name)

        with override_settings(NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url):
            options = {
                "course_ids": [self.valid_course_id],
                "certificate_download_url": self.valid_download_url,
            }

            self.command.set_arguments(options)

            self.assertEqual(self.command.batch_size, DEFAULTS["NAU_CERTIFICATE_BATCH_SIZE"])
            self.assertEqual(self.command.download_timeout, DEFAULTS["NAU_CERTIFICATE_DOWNLOAD_TIMEOUT"])
            self.assertEqual(self.command.max_workers, DEFAULTS["NAU_CERTIFICATE_MAX_WORKERS"])
            self.assertEqual(self.command.certificate_temp_folder, DEFAULTS["NAU_CERTIFICATE_TEMP_FOLDER"])

    @patch_export_course_certificates_to_zip
    @patch_generated_certificate
    def test_mixed_valid_and_invalid_course_ids(self, mock_generated_certificate, mock_export_task):
        """Test with a mix of valid and invalid course IDs."""
        valid_course_id = "course-v1:NAU+Demo+ValidCourse"
        invalid_course_id = "invalid-course-id"

        mock_certificates = MagicMock()
        mock_certificates.values_list.return_value = ["uuid1", "uuid2"]
        mock_generated_certificate.objects.filter.return_value = mock_certificates

        mock_export_task.delay.return_value = None

        with override_settings(NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url):
            options = {
                "course_ids": [valid_course_id, invalid_course_id],
                "certificate_download_url": self.valid_download_url,
            }
            self.command.set_arguments(options)
            self.command.export_pdfs()

        mock_export_task.delay.assert_called_once()

        output = self.command.stdout.getvalue()
        self.assertIn(f"Invalid course ID: {invalid_course_id}", output)
        self.assertIn("Task dispatched successfully for course course-v1:NAU+Demo+ValidCourse", output)

    def test_get_verify_uuids_by_course_key(self):
        """Test the get_verify_uuids_by_course_key method."""
        course_key = CourseKey.from_string(self.valid_course_id)
        expected_uuids = ["uuid1", "uuid2", "uuid3"]

        with self.patch_generated_certificate as mock_generated_certificate:
            mock_certificates = MagicMock()
            mock_certificates.values_list.return_value = expected_uuids
            mock_generated_certificate.objects.filter.return_value = mock_certificates

            result = self.command.get_verify_uuids_by_course_key(course_key)

            self.assertEqual(result, expected_uuids)
            mock_generated_certificate.objects.filter.assert_called_once_with(course_id=course_key)

    def test_validate_arguments_missing_course_ids(self):
        """Test validation when course_ids is empty."""
        self.command.course_ids = []
        self.command.certificate_download_url = self.valid_download_url
        self.command.batch_size = 100
        self.command.download_timeout = 60
        self.command.max_workers = 8

        with self.assertRaises(CommandError) as context:
            self.command.validate_arguments()

        self.assertIn("At least one course_id is required", str(context.exception))

    def test_validate_arguments_missing_download_url(self):
        """Test validation when certificate_download_url is missing."""
        self.command.course_ids = [self.valid_course_id]
        self.command.certificate_download_url = ""
        self.command.batch_size = 100
        self.command.download_timeout = 60
        self.command.max_workers = 8

        with self.assertRaises(CommandError) as context:
            self.command.validate_arguments()

        self.assertIn("certificate_download_url is required", str(context.exception))

    def test_validate_arguments_invalid_url(self):
        """Test validation with invalid URL."""
        self.command.course_ids = [self.valid_course_id]
        self.command.certificate_download_url = "not-a-valid-url"
        self.command.batch_size = 100
        self.command.download_timeout = 60
        self.command.max_workers = 8

        with self.assertRaises(CommandError) as context:
            self.command.validate_arguments()

        self.assertIn("Invalid certificate_download_url format", str(context.exception))

    def test_validate_arguments_invalid_batch_size(self):
        """Test validation with invalid batch size."""
        self.command.course_ids = [self.valid_course_id]
        self.command.certificate_download_url = self.valid_download_url
        self.command.batch_size = 0
        self.command.download_timeout = 60
        self.command.max_workers = 8

        with self.assertRaises(CommandError) as context:
            self.command.validate_arguments()

        self.assertIn("batch_size must be greater than 0", str(context.exception))

    def test_validate_arguments_invalid_timeout(self):
        """Test validation with invalid timeout."""
        self.command.course_ids = [self.valid_course_id]
        self.command.certificate_download_url = self.valid_download_url
        self.command.batch_size = 100
        self.command.download_timeout = 0
        self.command.max_workers = 8

        with self.assertRaises(CommandError) as context:
            self.command.validate_arguments()

        self.assertIn("download_timeout must be greater than 0", str(context.exception))

    def test_validate_arguments_invalid_max_workers(self):
        """Test validation with invalid max workers."""
        self.command.course_ids = [self.valid_course_id]
        self.command.certificate_download_url = self.valid_download_url
        self.command.batch_size = 100
        self.command.download_timeout = 60
        self.command.max_workers = 0

        with self.assertRaises(CommandError) as context:
            self.command.validate_arguments()

        self.assertIn("max_workers must be greater than 0", str(context.exception))

    def test_validate_arguments_valid_arguments(self):
        """Test validation with valid arguments."""
        self.command.course_ids = [self.valid_course_id]
        self.command.certificate_download_url = self.valid_download_url
        self.command.batch_size = 1
        self.command.download_timeout = 60
        self.command.max_workers = 8

        self.command.validate_arguments()

    @patch_export_course_certificates_to_zip
    @patch_generated_certificate
    def test_export_pdfs_with_exception(self, mock_generated_certificate, mock_export_task):
        """Test export_pdfs method when an exception occurs."""
        mock_certificates = MagicMock()
        mock_certificates.values_list.return_value = ["uuid1", "uuid2"]
        mock_generated_certificate.objects.filter.return_value = mock_certificates

        mock_export_task.delay.side_effect = Exception("Task failed")

        with override_settings(NAU_CERTIFICATE_DOWNLOAD_URL=self.valid_download_url):
            options = {
                "course_ids": [self.valid_course_id],
                "certificate_download_url": self.valid_download_url,
            }
            self.command.set_arguments(options)

            with self.assertRaises(Exception) as context:
                self.command.export_pdfs()

            self.assertEqual(str(context.exception), "Task failed")
