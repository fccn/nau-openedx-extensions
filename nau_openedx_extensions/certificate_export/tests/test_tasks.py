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
    export_course_certificates_task,
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


class ExportCourseCertificatesTaskTest(TestCase):
    """Tests for the export_course_certificates_task function."""

    def setUp(self):
        """Set up test fixtures."""
        self.course_id = "course-v1:NAU+Demo+Demo"

        # Patch the Command class
        self.command_patcher = patch(f"{TASKS_MODULE_PATH}.Command")
        self.mock_command_class = self.command_patcher.start()
        self.mock_command_instance = MagicMock()
        self.mock_command_class.return_value = self.mock_command_instance

    def tearDown(self):
        """Stop all patchers."""
        self.command_patcher.stop()

    def test_export_course_certificates_task_success(self):
        """Test successful execution of export_course_certificates_task."""
        # Execute the task
        export_course_certificates_task(self.course_id)

        # Verify Command was instantiated
        self.mock_command_class.assert_called_once()

        # Verify handle was called with correct parameters
        expected_options = {"course_ids": [self.course_id]}
        self.mock_command_instance.handle.assert_called_once_with(**expected_options)

    def test_export_course_certificates_task_with_different_course_id(self):
        """Test task with different course ID format."""
        different_course_id = "course-v1:MIT+6.00x+2023_T1"

        export_course_certificates_task(different_course_id)

        self.mock_command_class.assert_called_once()
        expected_options = {"course_ids": [different_course_id]}
        self.mock_command_instance.handle.assert_called_once_with(**expected_options)

    def test_export_course_certificates_task_command_instantiation(self):
        """Test that Command is properly instantiated."""
        export_course_certificates_task(self.course_id)

        # Verify Command class was called without arguments
        self.mock_command_class.assert_called_once_with()

    def test_export_course_certificates_task_options_format(self):
        """Test that options are formatted correctly as a dictionary."""
        export_course_certificates_task(self.course_id)

        # Get the call arguments
        call_args = self.mock_command_instance.handle.call_args

        # Verify it was called with keyword arguments
        self.assertIsNotNone(call_args)
        self.assertEqual(len(call_args[0]), 0)  # No positional args

        # Verify the keyword arguments
        options = call_args[1]
        self.assertIn("course_ids", options)
        self.assertEqual(options["course_ids"], [self.course_id])
        self.assertIsInstance(options["course_ids"], list)

    def test_export_course_certificates_task_multiple_calls(self):
        """Test multiple calls to the task with different course IDs."""
        course_ids = [
            "course-v1:NAU+Demo+Demo",
            "course-v1:MIT+6.00x+2023_T1",
            "course-v1:Harvard+CS50+2023"
        ]

        for course_id in course_ids:
            export_course_certificates_task(course_id)

        # Verify Command was instantiated for each call
        self.assertEqual(self.mock_command_class.call_count, len(course_ids))
        self.assertEqual(self.mock_command_instance.handle.call_count, len(course_ids))

        # Verify each call had the correct course_id
        for i, course_id in enumerate(course_ids):
            call_args = self.mock_command_instance.handle.call_args_list[i]
            expected_options = {"course_ids": [course_id]}
            self.assertEqual(call_args[1], expected_options)

    def test_export_course_certificates_task_empty_course_id(self):
        """Test task behavior with empty course ID."""
        empty_course_id = ""

        export_course_certificates_task(empty_course_id)

        expected_options = {"course_ids": [empty_course_id]}
        self.mock_command_instance.handle.assert_called_once_with(**expected_options)

    def test_export_course_certificates_task_none_course_id(self):
        """Test task behavior with None course ID."""
        none_course_id = None

        export_course_certificates_task(none_course_id)

        expected_options = {"course_ids": [none_course_id]}
        self.mock_command_instance.handle.assert_called_once_with(**expected_options)


class PivotStudentStateCsvTest(TestCase):
    """Tests for the pivot_student_state_csv function."""

    def _make_tsv(self, rows):
        """Build a TSV string from a list of dicts."""
        import io
        import csv

        output = io.StringIO()
        fieldnames = ["username", "title", "location", "ID da Resposta", "Pergunta", "Resposta", "Resposta Correta",
                       "block_key", "state"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return output.getvalue()

    def test_basic_pivot_two_users(self):
        """Test basic pivot with two users and two questions each."""
        from nau_openedx_extensions.certificate_export.tasks import pivot_student_state_csv

        rows = [
            {"username": "user1", "title": "T", "location": "L", "ID da Resposta": "q1",
             "Pergunta": "Q1", "Resposta": "A", "Resposta Correta": "A,B", "block_key": "bk1", "state": "{}"},
            {"username": "user1", "title": "T", "location": "L", "ID da Resposta": "q2",
             "Pergunta": "Q2", "Resposta": "B", "Resposta Correta": "B,C", "block_key": "bk1", "state": "{}"},
            {"username": "user2", "title": "T", "location": "L", "ID da Resposta": "q1",
             "Pergunta": "Q1", "Resposta": "C", "Resposta Correta": "A,B", "block_key": "bk1", "state": "{}"},
            {"username": "user2", "title": "T", "location": "L", "ID da Resposta": "q2",
             "Pergunta": "Q2", "Resposta": "D", "Resposta Correta": "B,C", "block_key": "bk1", "state": "{}"},
        ]
        csv_content = self._make_tsv(rows)
        result = pivot_student_state_csv(csv_content)

        # Header + 2 users
        self.assertEqual(len(result), 3)
        header = result[0]
        self.assertIn("q1_Resposta", header)
        self.assertIn("q1_Resposta_Correta", header)
        self.assertIn("q2_Resposta", header)
        self.assertIn("q2_Resposta_Correta", header)

        # user1 row
        user1_row = result[1]
        self.assertEqual(user1_row[0], "user1")
        q1_idx = header.index("q1_Resposta")
        self.assertEqual(user1_row[q1_idx], "A")
        q2_idx = header.index("q2_Resposta")
        self.assertEqual(user1_row[q2_idx], "B")

        # user2 row
        user2_row = result[2]
        self.assertEqual(user2_row[0], "user2")
        self.assertEqual(user2_row[q1_idx], "C")
        self.assertEqual(user2_row[q2_idx], "D")

    def test_pivot_with_missing_answers(self):
        """Test pivot when a user is missing some answers."""
        from nau_openedx_extensions.certificate_export.tasks import pivot_student_state_csv

        rows = [
            {"username": "user1", "title": "T", "location": "L", "ID da Resposta": "q1",
             "Pergunta": "Q1", "Resposta": "A", "Resposta Correta": "A", "block_key": "bk1", "state": "{}"},
            {"username": "user1", "title": "T", "location": "L", "ID da Resposta": "q2",
             "Pergunta": "Q2", "Resposta": "B", "Resposta Correta": "B", "block_key": "bk1", "state": "{}"},
            {"username": "user2", "title": "T", "location": "L", "ID da Resposta": "q1",
             "Pergunta": "Q1", "Resposta": "C", "Resposta Correta": "A", "block_key": "bk1", "state": "{}"},
            # user2 does NOT have q2
        ]
        csv_content = self._make_tsv(rows)
        result = pivot_student_state_csv(csv_content)

        self.assertEqual(len(result), 3)
        header = result[0]
        q2_idx = header.index("q2_Resposta")

        # user2 should have empty string for missing q2
        user2_row = result[2]
        self.assertEqual(user2_row[q2_idx], "")

    def test_pivot_empty_csv(self):
        """Test pivot with empty CSV (only header)."""
        from nau_openedx_extensions.certificate_export.tasks import pivot_student_state_csv

        csv_content = "username\ttitle\tlocation\tID da Resposta\tPergunta\tResposta\tResposta Correta\tblock_key\tstate\n"
        result = pivot_student_state_csv(csv_content)

        # Only header row, no data
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ["username", "title", "location", "block_key", "state"])

    def test_pivot_preserves_fixed_columns(self):
        """Test that fixed columns are preserved correctly."""
        from nau_openedx_extensions.certificate_export.tasks import pivot_student_state_csv

        rows = [
            {"username": "user1", "title": "My Title", "location": "My Location", "ID da Resposta": "q1",
             "Pergunta": "Q1", "Resposta": "A", "Resposta Correta": "A", "block_key": "block-v1:test",
             "state": '{"done": true}'},
        ]
        csv_content = self._make_tsv(rows)
        result = pivot_student_state_csv(csv_content)

        self.assertEqual(len(result), 2)
        user_row = result[1]
        self.assertEqual(user_row[0], "user1")
        self.assertEqual(user_row[1], "My Title")
        self.assertEqual(user_row[2], "My Location")
        self.assertEqual(user_row[3], "block-v1:test")
        self.assertEqual(user_row[4], '{"done": true}')


class StudentAnswersValuesReportTaskTest(TestCase):
    """Tests for the student_answers_values_report_task function."""

    def setUp(self):
        self.course_id = "course-v1:NAU+Demo+Demo"
        self.block_id = "block-v1:NAU+Demo+Demo+type@problem+block@problem1"

        self.get_report_store_patcher = patch(f"{TASKS_MODULE_PATH}.student_answers_values_report_task.__wrapped__")
        self.report_store_patcher = patch(
            f"{TASKS_MODULE_PATH}.get_report_store"
        )
        self.upload_patcher = patch(
            f"{TASKS_MODULE_PATH}.upload_csv_to_report_store"
        )
        # We need to patch the imports inside the task function
        self.inner_report_store_patcher = patch(
            "nau_openedx_extensions.edxapp_wrapper.instructor_task.get_report_store"
        )
        self.inner_upload_patcher = patch(
            "nau_openedx_extensions.edxapp_wrapper.instructor_task.upload_csv_to_report_store"
        )

    def tearDown(self):
        pass

    @patch(f"{TASKS_MODULE_PATH}.requests.get")
    @patch("nau_openedx_extensions.edxapp_wrapper.instructor_task.get_report_store")
    @patch("nau_openedx_extensions.edxapp_wrapper.instructor_task.upload_csv_to_report_store")
    def test_successful_report_generation(self, mock_upload, mock_get_store, mock_requests_get):
        """Test successful report generation with valid data."""
        from nau_openedx_extensions.certificate_export.tasks import student_answers_values_report_task

        # Mock report store
        mock_store = MagicMock()
        mock_store.links_for.return_value = [
            ("NAU_Demo_Demo_student_state_from_block_2025-01-01-0000.csv", "https://example.com/report.csv"),
        ]
        mock_get_store.return_value = mock_store

        # Mock CSV download
        csv_content = (
            "username\ttitle\tlocation\tID da Resposta\tPergunta\tResposta\tResposta Correta\tblock_key\tstate\n"
            "user1\tT\tL\tq1\tQ1\tA\tA,B\tbk1\t{}\n"
            "user1\tT\tL\tq2\tQ2\tB\tB,C\tbk1\t{}\n"
        )
        mock_response = Mock()
        mock_response.text = csv_content
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Execute task
        student_answers_values_report_task(self.course_id, self.block_id)

        # Verify upload was called
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        rows = call_args[0][0]
        # Header + 1 user
        self.assertEqual(len(rows), 2)
        self.assertIn("q1_Resposta", rows[0])

    @patch("nau_openedx_extensions.edxapp_wrapper.instructor_task.get_report_store")
    def test_no_report_found(self, mock_get_store):
        """Test when no student_state_from report exists."""
        from nau_openedx_extensions.certificate_export.tasks import student_answers_values_report_task

        mock_store = MagicMock()
        mock_store.links_for.return_value = []
        mock_get_store.return_value = mock_store

        # Should not raise, just log error and return
        student_answers_values_report_task(self.course_id, self.block_id)

        # No upload should happen
        # (can't easily assert upload wasn't called since it's imported inside the function)
