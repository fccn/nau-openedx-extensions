"""
Export all PDF course certificates to a zip file using Celery.

This command allows you to export course certificates as PDFs for specified courses.
The certificates will be processed in batches and exported to a zip file.

Configuration:

- NAU_CERTIFICATE_DOWNLOAD_URL: The domain to use to download the certificates (Required)
- NAU_CERTIFICATE_BATCH_SIZE: Number of certificates to process in each batch (Optional)
- NAU_CERTIFICATE_TEMP_FOLDER: The path to the temporary folder (Optional)
- NAU_CERTIFICATE_DOWNLOAD_TIMEOUT: Timeout in seconds for each download (Optional)
- NAU_CERTIFICATE_MAX_WORKERS: Maximum number of parallel downloads (Optional)

There are 3 configuration levels:

1. Command line arguments
2. Django settings
3. Default values

The command line arguments override the Django settings, and the Django settings override the default values.

Example usage:

Export certificates for a single course:
    python manage.py lms export_course_certificates_pdfs course_id_1

Export certificates for multiple courses:
    python manage.py lms export_course_certificates_pdfs course_id_1 course_id_2 course_id_3

Export certificates with a custom download URL:
    python manage.py lms export_course_certificates_pdfs course_id_1 \
        --certificate-download-url=https://course-certificate.dev.nau.fccn.pt/attachment/certificates

Export certificates with a custom batch size:
    python manage.py lms export_course_certificates_pdfs course_id_1 --batch-size=50

Export certificates with a custom temporary folder:
    python manage.py lms export_course_certificates_pdfs course_id_1 --certificate-temp-folder=/path/to/temp/folder

Export certificates with a custom download timeout:
    python manage.py lms export_course_certificates_pdfs course_id_1 --download-timeout=60

Export certificates with a custom maximum number of workers:
    python manage.py lms export_course_certificates_pdfs course_id_1 --max-workers=8
"""

from typing import Any, List

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.certificate_export.tasks import export_course_certificates_to_zip
from nau_openedx_extensions.edxapp_wrapper.certificates import GeneratedCertificate

DEFAULTS = {
    "NAU_CERTIFICATE_BATCH_SIZE": 100,
    "NAU_CERTIFICATE_TEMP_FOLDER": "/tmp/export_certificates",
    "NAU_CERTIFICATE_DOWNLOAD_TIMEOUT": 60,
    "NAU_CERTIFICATE_MAX_WORKERS": 8,
}


def get_setting(name: str) -> Any:
    """Get setting with default value."""
    return getattr(settings, name, DEFAULTS.get(name))


class Command(BaseCommand):
    """Command to export course certificates as PDFs and compress them into a ZIP file."""

    help = "Export all PDF course certificates to a zip file using Celery."

    course_ids: List[str]
    certificate_download_url: str
    batch_size: int
    certificate_temp_folder: str
    download_timeout: int
    max_workers: int

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "course_ids",
            nargs="+",
            help="List of course IDs to export certificates for",
        )
        parser.add_argument(
            "--certificate-download-url",
            help="The domain to use to download the certificates",
            required=False,
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            help="Number of certificates to process in each batch",
            required=False,
        )
        parser.add_argument(
            "--certificate-temp-folder",
            help="The path to the temporary folder",
            required=False,
        )
        parser.add_argument(
            "--download-timeout",
            type=int,
            help="Timeout in seconds for each download",
            required=False,
        )
        parser.add_argument(
            "--max-workers",
            type=int,
            help="Maximum number of parallel downloads",
            required=False,
        )

    def validate_arguments(self) -> None:
        """Validate the command arguments."""
        if not self.course_ids:
            raise CommandError("At least one course_id is required")

        if not self.certificate_download_url:
            raise CommandError("certificate_download_url is required")

        try:
            URLValidator()(self.certificate_download_url)
        except ValidationError as exc:
            raise CommandError("Invalid certificate_download_url format") from exc

        if self.batch_size <= 0:
            raise CommandError("batch_size must be greater than 0")

        if self.download_timeout <= 0:
            raise CommandError("download_timeout must be greater than 0")

        if self.max_workers <= 0:
            raise CommandError("max_workers must be greater than 0")

    def log_msg(self, msg: str) -> None:
        """Log a message to stdout with proper formatting."""
        self.stdout.write(self.style.SUCCESS(msg))
        self.stdout.flush()

    def set_arguments(self, options: dict) -> None:
        """Set the command arguments."""
        self.course_ids = options["course_ids"]
        self.certificate_download_url = options.get("certificate_download_url") or get_setting(
            "NAU_CERTIFICATE_DOWNLOAD_URL"
        )
        self.batch_size = options.get("batch_size") or get_setting("NAU_CERTIFICATE_BATCH_SIZE")
        self.certificate_temp_folder = options.get("certificate_temp_folder") or get_setting(
            "NAU_CERTIFICATE_TEMP_FOLDER"
        )
        self.download_timeout = options.get("download_timeout") or get_setting("NAU_CERTIFICATE_DOWNLOAD_TIMEOUT")
        self.max_workers = options.get("max_workers") or get_setting("NAU_CERTIFICATE_MAX_WORKERS")

        self.validate_arguments()

    def export_pdfs(self) -> None:
        """
        Export all PDF course certificates to a zip file using Celery.

        Raises:
            InvalidKeyError: If any course_id is invalid
        """
        for course_id in self.course_ids:
            try:
                course_key = CourseKey.from_string(course_id)
            except InvalidKeyError:
                self.log_msg(f"Invalid course ID: {course_id}")
                continue

            verify_uuids = self.get_verify_uuids_by_course_key(course_key)

            if not verify_uuids:
                self.log_msg(f"No certificates found for course {course_id}")
                continue

            self.log_msg(f"Dispatching export task for course {course_id} with {len(verify_uuids)} certificates...")
            export_course_certificates_to_zip.delay(
                course_id,
                verify_uuids,
                self.certificate_download_url,
                self.certificate_temp_folder,
                self.batch_size,
                self.download_timeout,
                self.max_workers,
            )
            self.log_msg(f"Task dispatched successfully for course {course_id}")

    def get_verify_uuids_by_course_key(self, course_key: CourseKey) -> list[str]:
        """
        Get the verify UUIDs for each certificate of a course.

        Args:
            course_key (CourseKey): The course key

        Returns:
            list[str]: The verify UUIDs
        """
        generated_certificates = GeneratedCertificate.objects.filter(course_id=course_key)
        return list(generated_certificates.values_list("verify_uuid", flat=True))

    def handle(self, *args, **options) -> None:
        """Handle the command execution."""
        try:
            self.set_arguments(options)

            self.log_msg("Starting certificate export process...\n")
            self.log_msg(f"Processing {len(self.course_ids)} courses")
            self.log_msg(f"Using download URL: {self.certificate_download_url}")
            self.log_msg(f"Batch size: {self.batch_size}")
            self.log_msg(f"Download timeout: {self.download_timeout}")
            self.log_msg(f"Max workers: {self.max_workers}\n")

            self.export_pdfs()

            self.log_msg("Certificate export process completed successfully!")
        except CommandError as e:
            raise e
        except Exception as e:
            raise CommandError(f"Certificate export failed: {str(e)}") from e
