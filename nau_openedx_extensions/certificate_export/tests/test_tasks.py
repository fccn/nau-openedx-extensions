"""
Unit tests for certificate export tasks.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest import TestCase, mock
from unittest.mock import MagicMock, Mock, call, mock_open, patch

from requests.exceptions import RequestException, Timeout

from nau_openedx_extensions.certificate_export.exceptions import CertificateCompressionError
from nau_openedx_extensions.certificate_export.tasks import (
    compress_and_upload_all,
    download_batch,
    export_course_certificates_to_zip,
)

TASKS_MODULE_PATH = "nau_openedx_extensions.certificate_export.tasks"


class ExportCourseCertificatesToZipTest(TestCase):
    """Tests for the export_course_certificates_to_zip task."""

    def setUp(self):
        self.course_id = "course-v1:NAU+Demo+Demo"
        self.certificate_download_url = "https://example.com"
        self.certificate_temp_folder = "/tmp/certs"
        self.download_timeout = 10
        self.max_workers = 2
        self.batch_size = 4
        self.shared_temp_folder = os.path.join(self.certificate_temp_folder, self.course_id)

        self.mkdir_patcher = patch(f"{TASKS_MODULE_PATH}.Path.mkdir")
        self.download_batch_patcher = patch(f"{TASKS_MODULE_PATH}.download_batch")
        self.compress_patcher = patch(f"{TASKS_MODULE_PATH}.compress_and_upload_all")
        self.chord_patcher = patch(f"{TASKS_MODULE_PATH}.chord")

        self.mock_mkdir = self.mkdir_patcher.start()
        self.mock_download_batch = self.download_batch_patcher.start()
        self.mock_compress = self.compress_patcher.start()
        self.mock_chord = self.chord_patcher.start()

        self.mock_download_batch.s = MagicMock(side_effect=lambda folder, urls, **kwargs: f"task-{','.join(urls)}")
        self.mock_compress.s = MagicMock(return_value="compression-task")

    def tearDown(self):
        """Stop all patchers."""
        self.mkdir_patcher.stop()
        self.download_batch_patcher.stop()
        self.compress_patcher.stop()
        self.chord_patcher.stop()

    def _call_export_function(self, verify_uuids, batch_size=None):
        return export_course_certificates_to_zip(
            self.course_id,
            verify_uuids,
            self.certificate_download_url,
            self.certificate_temp_folder,
            batch_size or self.batch_size,
            self.download_timeout,
            self.max_workers,
        )

    def test_multiple_batches_and_chord_called(self):
        """Test that multiple batches are created and chord is called correctly."""
        verify_uuids = [f"uuid-{i}" for i in range(10)]
        self._call_export_function(verify_uuids)

        self.mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        expected_batches = [verify_uuids[i: i + self.batch_size] for i in range(0, len(verify_uuids), self.batch_size)]

        self.assertEqual(self.mock_download_batch.s.call_count, len(expected_batches))
        for batch in expected_batches:
            expected_urls = [f"{self.certificate_download_url}/{uuid}" for uuid in batch]
            self.mock_download_batch.s.assert_any_call(
                self.shared_temp_folder,
                expected_urls,
                download_timeout=self.download_timeout,
                max_workers=self.max_workers,
            )

        self.mock_chord.assert_called_once()
        self.mock_compress.s.assert_called_once_with(self.course_id, self.shared_temp_folder)

    def test_empty_uuid_list_does_not_trigger_download(self):
        """Test that no downloads are triggered when UUID list is empty."""
        self._call_export_function([])

        self.mock_mkdir.assert_called_once()
        self.mock_download_batch.s.assert_not_called()
        self.mock_chord.assert_not_called()
        self.mock_compress.s.assert_not_called()

    def test_single_batch_when_batch_size_exceeds_uuids(self):
        """Test that a single batch is created when batch size exceeds UUID count."""
        verify_uuids = [f"uuid-{i}" for i in range(3)]
        self._call_export_function(verify_uuids, batch_size=10)

        self.mock_download_batch.s.assert_called_once()
        self.mock_chord.assert_called_once()

    def test_mkdir_raises_exception(self):
        """Test that mkdir exceptions are properly propagated."""
        self.mock_mkdir.side_effect = OSError("mkdir error")

        with self.assertRaises(OSError) as context:
            self._call_export_function(["uuid-1"])

        self.assertEqual(str(context.exception), "mkdir error")


class CompressAndUploadAllTest(TestCase):
    """Tests for the compress_and_upload_all task."""

    def setUp(self):
        self.course_id = "course-v1:NAU+Demo+Demo"
        self.shared_temp_folder = "/tmp/certs/course-v1:NAU+Demo+Demo"
        self.zip_path = f"{self.shared_temp_folder}.zip"

        self.path_patcher = patch(f"{TASKS_MODULE_PATH}.Path")
        self.shutil_patcher = patch(f"{TASKS_MODULE_PATH}.shutil")
        self.os_patcher = patch(f"{TASKS_MODULE_PATH}.os")
        self.upload_patcher = patch(f"{TASKS_MODULE_PATH}.upload_zip_to_report_store")

        self.mock_path = self.path_patcher.start()
        self.mock_shutil = self.shutil_patcher.start()
        self.mock_os = self.os_patcher.start()
        self.mock_upload = self.upload_patcher.start()

        self.mock_path_instance = MagicMock()
        self.mock_path.return_value = self.mock_path_instance
        self.mock_path_instance.glob.return_value = ["cert1.pdf", "cert2.pdf"]

    def tearDown(self):
        """Stop all patchers."""
        self.path_patcher.stop()
        self.shutil_patcher.stop()
        self.os_patcher.stop()
        self.upload_patcher.stop()

    def test_successful_compression_and_upload(self):
        """Test successful compression and upload of certificates."""
        self.mock_os.path.exists.return_value = True

        with patch(f"{TASKS_MODULE_PATH}.open", mock.mock_open(read_data=b"zip file content")) as mock_file:
            compress_and_upload_all([], self.course_id, self.shared_temp_folder)

        self.mock_shutil.make_archive.assert_called_once_with(self.shared_temp_folder, "zip", self.shared_temp_folder)
        self.mock_upload.assert_called_once()
        self.mock_shutil.rmtree.assert_called_once_with(self.shared_temp_folder, ignore_errors=True)
        self.mock_os.remove.assert_called_once_with(self.zip_path)

        # Verify that the file was opened correctly
        mock_file.assert_called_once_with(self.zip_path, "rb")

    def test_no_pdfs_found(self):
        """Test when no PDFs are found in the folder."""
        self.mock_path_instance.glob.return_value = []

        compress_and_upload_all([], self.course_id, self.shared_temp_folder)

        self.mock_shutil.make_archive.assert_not_called()
        self.mock_upload.assert_not_called()
        self.mock_shutil.rmtree.assert_called_once_with(self.shared_temp_folder, ignore_errors=True)

    def test_compression_error(self):
        """Test when compression fails."""
        self.mock_shutil.make_archive.side_effect = Exception("Compression failed")

        with self.assertRaises(CertificateCompressionError):
            compress_and_upload_all([], self.course_id, self.shared_temp_folder)

        self.mock_shutil.rmtree.assert_called_once_with(self.shared_temp_folder, ignore_errors=True)
        self.mock_os.remove.assert_called_once_with(self.zip_path)


class DownloadBatchTest(TestCase):
    """Test cases for download_batch function"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_task = Mock()
        self.mock_task.retry = Mock(side_effect=Exception("Retry called"))

        self.temp_folder = tempfile.mkdtemp()
        self.urls = ["https://example.com/cert1.pdf", "https://example.com/cert2.pdf", "https://example.com/cert3.pdf"]
        self.download_timeout = 30
        self.max_workers = 3

    def tearDown(self):
        """Clean up after each test method."""
        if Path(self.temp_folder).exists():
            shutil.rmtree(self.temp_folder)

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    def test_successful_download_all_files(self, mock_sanitize, mock_get):
        """Test successful download of all files"""
        mock_sanitize.side_effect = lambda x: x.split("/")[-1]
        mock_response = Mock()
        mock_response.content = b"fake pdf content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch("builtins.open", mock_open()) as mock_file:
            # pylint: disable=no-value-for-parameter
            result = download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        self.assertEqual(len(result), 3)
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_file.call_count, 3)

        expected_calls = [call(url, timeout=self.download_timeout) for url in self.urls]
        mock_get.assert_has_calls(expected_calls, any_order=True)

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    @patch(f"{TASKS_MODULE_PATH}.logger")
    def test_skip_existing_files(self, mock_logger, mock_sanitize, mock_get):
        """Test that existing files are skipped"""
        mock_sanitize.side_effect = lambda x: x.split("/")[-1]

        existing_files = []
        for url in self.urls[:2]:
            filename = url.split("/")[-1]
            file_path = Path(self.temp_folder) / filename
            file_path.write_text("existing content")
            existing_files.append(str(file_path))

        mock_response = Mock()
        mock_response.content = b"new content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch("builtins.open", mock_open()) as mock_file:
            # pylint: disable=no-value-for-parameter
            result = download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        self.assertEqual(len(result), 3)
        mock_get.assert_called_once_with(self.urls[2], timeout=self.download_timeout)
        mock_file.assert_called_once()

        expected_skip_calls = [
            call(f"File already exists, skipping: {existing_files[0]}"),
            call(f"File already exists, skipping: {existing_files[1]}"),
        ]
        mock_logger.info.assert_has_calls(expected_skip_calls, any_order=True)

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    def test_partial_download_failure_raises_exception(self, mock_sanitize, mock_get):
        """Test that partial download failure raises CertificateDownloadError"""
        mock_sanitize.side_effect = lambda x: x.split("/")[-1]

        def side_effect_get(url):
            if url == self.urls[0]:
                mock_response = Mock()
                mock_response.content = b"content"
                mock_response.raise_for_status = Mock()
                return mock_response
            else:
                raise RequestException("Network error")

        mock_get.side_effect = side_effect_get

        with patch("builtins.open", mock_open()):
            with self.assertRaises(Exception) as context:
                # pylint: disable=no-value-for-parameter
                download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        self.assertEqual(context.exception.args[0], "Some downloads failed, retrying batch...")

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    @patch(f"{TASKS_MODULE_PATH}.logger")
    def test_request_timeout_handled_gracefully(self, mock_logger, mock_sanitize, mock_get):
        """Test that request timeouts are handled gracefully"""
        mock_sanitize.side_effect = lambda x: x.split("/")[-1]
        mock_get.side_effect = Timeout("Request timed out")

        with self.assertRaises(Exception):
            # pylint: disable=no-value-for-parameter
            download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        self.assertEqual(mock_logger.warning.call_count, 3)
        for url in self.urls:
            mock_logger.warning.assert_any_call(f"Failed to download {url}: Request timed out")

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    @patch(f"{TASKS_MODULE_PATH}.logger")
    def test_http_error_handled_gracefully(self, mock_logger, mock_sanitize, mock_get):
        """Test that HTTP errors are handled gracefully"""
        mock_sanitize.side_effect = lambda x: x.split("/")[-1]
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = RequestException("404 Not Found")
        mock_get.return_value = mock_response

        with self.assertRaises(Exception):
            # pylint: disable=no-value-for-parameter
            download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        self.assertEqual(mock_logger.warning.call_count, 3)

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    @patch(f"{TASKS_MODULE_PATH}.logger")
    def test_file_write_error_handled(self, mock_logger, mock_sanitize, mock_get):
        """Test that file write errors are handled gracefully"""
        mock_sanitize.side_effect = lambda x: x.split("/")[-1]
        mock_response = Mock()
        mock_response.content = b"content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = IOError("Permission denied")

            with self.assertRaises(Exception):
                # pylint: disable=no-value-for-parameter
                download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        self.assertEqual(mock_logger.error.call_count, 4)

    def test_empty_urls_list(self):
        """Test behavior with empty URLs list"""
        # pylint: disable=no-value-for-parameter
        result = download_batch(self.temp_folder, [], self.download_timeout, self.max_workers)

        self.assertEqual(result, [])

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    def test_sanitize_filename_called(self, mock_sanitize, mock_get):
        """Test that sanitize_filename is called for each URL"""
        mock_sanitize.side_effect = lambda x: f"sanitized_{x.split('/')[-1]}"
        mock_response = Mock()
        mock_response.content = b"content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch("builtins.open", mock_open()):
            # pylint: disable=no-value-for-parameter
            download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        self.assertEqual(mock_sanitize.call_count, 3)
        expected_calls = [call(url.split("/")[-1]) for url in self.urls]
        mock_sanitize.assert_has_calls(expected_calls, any_order=True)

    @patch(f"{TASKS_MODULE_PATH}.ThreadPoolExecutor")
    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    def test_thread_pool_executor_configuration(self, mock_sanitize, mock_get, mock_executor_class):
        """Test that ThreadPoolExecutor is configured with correct max_workers"""
        mock_executor = Mock()
        mock_executor.__enter__ = Mock(return_value=mock_executor)
        mock_executor.__exit__ = Mock(return_value=None)
        mock_executor.submit = Mock()
        mock_executor_class.return_value = mock_executor

        mock_sanitize.side_effect = lambda x: x.split("/")[-1]
        mock_response = Mock()
        mock_response.content = b"content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch(f"{TASKS_MODULE_PATH}.as_completed", return_value=iter([])):
            with self.assertRaises(Exception):  # Will raise due to partial failure
                # pylint: disable=no-value-for-parameter
                download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        mock_executor_class.assert_called_once_with(max_workers=self.max_workers)

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch(f"{TASKS_MODULE_PATH}.sanitize_filename")
    @patch(f"{TASKS_MODULE_PATH}.logger")
    def test_successful_download_logs_correctly(self, mock_logger, mock_sanitize, mock_get):
        """Test that successful downloads are logged correctly"""
        mock_sanitize.side_effect = lambda x: x.split("/")[-1]
        mock_response = Mock()
        mock_response.content = b"content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with patch("builtins.open", mock_open()):
            # pylint: disable=no-value-for-parameter
            download_batch(self.temp_folder, self.urls, self.download_timeout, self.max_workers)

        # Assert
        self.assertEqual(mock_logger.info.call_count, 3)
        for url in self.urls:
            filename = url.split("/")[-1]
            expected_path = str(Path(self.temp_folder) / filename)
            mock_logger.info.assert_any_call(f"Downloaded file: {expected_path}")
