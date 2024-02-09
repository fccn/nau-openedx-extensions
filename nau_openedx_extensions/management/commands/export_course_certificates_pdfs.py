"""
Export all PDF course certificates to a zip file and upload it to the `GRADES_DOWNLOAD` storage.

You can skip the `certificate_download_domain` parameter on production environment.

To manually develop the script you can edit it on the fly and execute it.
    docker cp export_course_certificates_pdfs.py \
        openedx_lms:/openedx/venv/lib/python3.8/site-packages/nau_openedx_extensions/management/\
            commands/export_course_certificates_pdfs.py && docker exec -i openedx_lms python \
                manage.py lms export_course_certificates_pdfs \
                    --certificate_download_domain course-certificate.dev.nau.fccn.pt \
                        course-v1:FCT+CTC101x+2020_T2
"""
import os
import shutil
from datetime import datetime

import requests  # lint-amnesty, pylint: disable=import-error
from common.djangoapps.util.query import use_read_replica_if_available  # lint-amnesty, pylint: disable=import-error
from django.conf import settings
from django.core.management.base import BaseCommand
from lms.djangoapps.certificates.models import GeneratedCertificate  # lint-amnesty, pylint: disable=import-error
from lms.djangoapps.instructor_task.tasks_helper.utils import (  # lint-amnesty, pylint: disable=import-error
    upload_zip_to_report_store,
)
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.site_configuration.models import (  # lint-amnesty, pylint: disable=import-error
    SiteConfiguration,
)
from pytz import UTC


def delete_recursive(folder):
    """
    Delete a folder recursively.
    """
    try:
        shutil.rmtree(folder)
    except FileNotFoundError:
        # directory doesn't exist
        pass


def create_folder(path):
    """
    Crete a folder using the path.
    """
    try:
        os.makedirs(path)
    except FileExistsError:
        # directory already exists
        pass


def save_file(filename, content):
    """
    Save the content to a file.
    """
    with open(filename, "w") as certificates_file:
        certificates_file.write(content)


def download_file(base_folder, url):
    """
    Download a file from an URL to a folder, by default use the filename header as the name of the
    file.
    """
    response = requests.get(url, timeout=60)
    filename = base_folder + "/"
    if "content-disposition" in response.headers:
        content_disposition = response.headers["content-disposition"]
        filename += content_disposition.split("filename=")[1]
    else:
        filename += url.split("/")[-1]
    with open(filename, mode="wb") as file:
        file.write(response.content)
    file.close()


class Command(BaseCommand):
    """
    Export all PDF course certificates with its links to a csv file and upload it to the
    `GRADES_DOWNLOAD` storage.
    """

    output_base_folder = getattr(
        settings,
        "NAU_EXPORT_COURSE_CERTIFICATES_PDFS_TEMP_FOLDER",
        "/tmp/export_certificates",
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--certificate_download_domain",
            default="course-certificate.nau.edu.pt",
            help="The domain to use to download the certificates",
        )
        parser.add_argument("course_ids", nargs="+", metavar="course_id")

    def log_msg(self, msg):
        self.stdout.write(msg)
        self.stdout.flush()

    def handle(self, *args, **options):
        """
        Execute the command
        """
        certificate_download_domain = options["certificate_download_domain"]
        course_ids = options["course_ids"]
        certificate_download_pdf_url = getattr(
            settings,
            "NAU_CERTIFICATE_DOWNLOAD_PDF_URL",
            f"https://{certificate_download_domain}/attachment/certificates/",
        )

        for course_id in course_ids:
            course_key = CourseKey.from_string(course_id)

            start_date = datetime.now(UTC)

            course_generated_certificates = use_read_replica_if_available(
                GeneratedCertificate.objects.filter(course_id=course_id)
            )
            course_certificate_folder = self.output_base_folder + "/" + course_id
            delete_recursive(course_certificate_folder)
            create_folder(course_certificate_folder)

            # iterate each certificate and append each certificate as a row
            count = 0
            certificate_links_total = len(course_generated_certificates)

            for certificate in course_generated_certificates:
                certificate_download_pdf_link = (
                    certificate_download_pdf_url + certificate.verify_uuid
                )
                download_file(course_certificate_folder, certificate_download_pdf_link)
                count += 1
                self.log_msg(f"Downloading {count}/{certificate_links_total}")

            self.log_msg(
                "Compressing output to a single zip file - "
                + course_certificate_folder
                + ".zip"
            )
            shutil.make_archive(
                course_certificate_folder, "zip", course_certificate_folder
            )

            with open(course_certificate_folder + ".zip", "rb") as zip_file:
                upload_zip_to_report_store(
                    zip_file,
                    "export_course_certificates_pdfs",
                    course_key,
                    start_date,
                )
            delete_recursive(course_certificate_folder)

            lms_root_url = SiteConfiguration.get_value_for_org(
                course_key.org, "LMS_ROOT_URL", settings.LMS_ROOT_URL
            )
            lms_instructor_data_download_url = (
                f"{lms_root_url}/courses/{course_id}/instructor#view-data_download"
            )
            self.log_msg(
                f"You can confirm the existence of the file on: {lms_instructor_data_download_url}"
            )
