"""
Celery tasks for certificate export functionality.

This module defines asynchronous tasks for exporting course certificates in multiple formats:
- CSV file export for certificates information.
- ZIP file export for PDF certificates.

The tasks are designed to be executed in the background using Celery.

Main tasks:

    - export_course_certificates_task: Exports course certificates information as a CSV file
      and uploads it to the specified storage.

    - export_course_certificates_to_zip: Downloads, compresses course certificates
      in PDF format as a ZIP file and uploads it to the specified storage.

      PDF Export Workflow:
        1. Split certificates into batches.
        2. Download each batch in parallel.
        3. Compress all downloaded files.
        4. Upload the final ZIP to the report store.

      Queue Configuration:
        For the high memory celery tasks, we use the `edx.lms.core.high_mem` queue, but
        this queue can be overridden by the `NAU_CERTIFICATE_QUEUE` Django setting.

Dependencies:
    - Celery: Used for task management.
    - Command: The management command responsible for handling the certificate export logic.
"""

import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests
from celery import chord, shared_task
from django.conf import settings
from opaque_keys.edx.keys import CourseKey
from requests.exceptions import RequestException

from nau_openedx_extensions.certificate_export.exceptions import CertificateCompressionError, CertificateDownloadError
from nau_openedx_extensions.certificate_export.management.commands.export_course_certificates import Command
from nau_openedx_extensions.certificate_export.utils import sanitize_filename
from nau_openedx_extensions.edxapp_wrapper.instructor_task import upload_zip_to_report_store

logger = logging.getLogger(__name__)


@shared_task
def export_course_certificates_task(course_id):
    """
    Celery task to export course certificates as a CSV file.
    """
    command = Command()
    options = {"course_ids": [course_id]}
    command.handle(**options)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue=getattr(settings, "NAU_CERTIFICATE_QUEUE", settings.HIGH_MEM_QUEUE),
)
def download_batch(
    self,
    shared_temp_folder: str,
    urls: List[str],
    download_timeout: int,
    max_workers: int,
) -> List[str]:
    """
    Download a batch of certificates in parallel. Retries on partial or total failure.
    This task should not be called directly, it is used by the `export_course_certificates_to_zip` task.

    Args:
        shared_temp_folder (str): Path to the shared temporary folder
        urls (List[str]): List of URLs to download
        download_timeout (int): Timeout in seconds for each download.
        max_workers (int): Maximum number of parallel downloads.

    Returns:
        List[str]: List of paths to downloaded files

    Raises:
        CertificateDownloadError: If there is an error downloading the certificates
    """
    try:
        Path(shared_temp_folder).mkdir(parents=True, exist_ok=True)
        downloaded = []

        def download(url: str) -> Optional[str]:
            try:
                filename = url.split("/")[-1]
                filename = sanitize_filename(filename)
                path = Path(shared_temp_folder) / filename

                if path.exists():
                    logger.info(f"File already exists, skipping: {path}")
                    return str(path)

                response = requests.get(url, timeout=download_timeout)
                response.raise_for_status()

                with open(path, "wb") as file:
                    file.write(response.content)

                logger.info(f"Downloaded file: {path}")
                return str(path)

            except RequestException as e:
                logger.warning(f"Failed to download {url}: {e}")
                return None
            except Exception as e:  # pylint: disable=broad-except
                logger.error(f"Unexpected error downloading {url}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(download, url) for url in urls]
            for future in as_completed(futures, timeout=download_timeout):
                result = future.result()
                if result:
                    downloaded.append(result)

        if len(downloaded) < len(urls):
            raise CertificateDownloadError("Some downloads failed, retrying batch...")

        return downloaded

    except Exception as exc:
        logger.error(f"Batch download failed: {exc}. Retrying...")
        raise self.retry(exc=exc)


@shared_task(queue=getattr(settings, "NAU_CERTIFICATE_QUEUE", settings.HIGH_MEM_QUEUE))
def compress_and_upload_all(_: List[str], course_id: str, shared_temp_folder: str) -> None:
    """
    Compress and upload all downloaded certificates to the report store.
    This task should not be called directly, it is used by the `export_course_certificates_to_zip` task.

    Args:
        _ (List[str]): Result of the previous task. Not used in this task.
        course_id (str): ID of the course
        shared_temp_folder (str): Path to the shared temporary folder

    Raises:
        CertificateCompressionError: If there is an error compressing or uploading the certificates
    """
    zip_path = f"{shared_temp_folder}.zip"

    try:
        if not any(Path(shared_temp_folder).glob("*.pdf")):
            logger.warning(f"No PDFs found in {shared_temp_folder}")
            return

        shutil.make_archive(shared_temp_folder, "zip", shared_temp_folder)

        with open(zip_path, "rb") as f:
            upload_zip_to_report_store(
                f,
                "export_course_certificates_pdfs",
                CourseKey.from_string(course_id),
                datetime.now(),
            )

        logger.info(f"Uploaded ZIP for course {course_id}")
    except Exception as e:
        logger.error(f"Error compressing/uploading final zip: {e}")
        raise CertificateCompressionError(f"Failed to compress/upload certificates: {e}") from e
    finally:
        shutil.rmtree(shared_temp_folder, ignore_errors=True)
        if os.path.exists(zip_path):
            os.remove(zip_path)


@shared_task
def export_course_certificates_to_zip(
    course_id: str,
    verify_uuids: List[str],
    certificate_download_url: str,
    certificate_temp_folder: str,
    batch_size: int,
    download_timeout: int,
    max_workers: int,
) -> None:
    """
    Export course certificates to a ZIP file.

    Args:
        course_id (str): ID of the course
        verify_uuids (List[str]): List of verification UUIDs for the certificates
        certificate_download_url (str): URL to download the certificates
        certificate_temp_folder (str): Path to the temporary folder
        batch_size (int): Number of certificates to download in parallel.
        download_timeout (int): Timeout in seconds for each download.
        max_workers (int): Maximum number of parallel downloads.
    """
    shared_temp_folder = os.path.join(certificate_temp_folder, course_id)
    Path(shared_temp_folder).mkdir(parents=True, exist_ok=True)

    batches = [verify_uuids[uuid: uuid + batch_size] for uuid in range(0, len(verify_uuids), batch_size)]

    download_tasks = [
        download_batch.s(
            shared_temp_folder,
            [f"{certificate_download_url}/{uuid}" for uuid in batch],
            download_timeout=download_timeout,
            max_workers=max_workers,
        )  # type: ignore
        for batch in batches
    ]

    if not download_tasks:
        return

    # When all downloads are done, compress and upload everything
    chord(download_tasks)(compress_and_upload_all.s(course_id, shared_temp_folder))  # type: ignore
