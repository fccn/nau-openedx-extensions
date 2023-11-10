"""
Export all PDF course certificates with its links to a csv file and upload it to the
`GRADES_DOWNLOAD` storage.

To manually develop the script you can edit it on the fly and execute it.
docker cp export_course_certificates.py \
    openedx_lms:/openedx/venv/lib/python3.8/site-packages/nau_openedx_extensions/\
        management/commands/export_course_certificates.py && \
    docker exec -i openedx_lms python manage.py lms export_course_certificates \
        course-v1:FCT+CTC101x+2020_T2
"""
from datetime import datetime

from common.djangoapps.util.query import use_read_replica_if_available  # lint-amnesty, pylint: disable=import-error
from django.conf import settings
from django.core.management.base import BaseCommand
from lms.djangoapps.certificates.models import GeneratedCertificate  # lint-amnesty, pylint: disable=import-error
from lms.djangoapps.instructor_task.tasks_helper.utils import (  # lint-amnesty, pylint: disable=import-error
    upload_csv_to_report_store,
)
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.site_configuration.models import (  # lint-amnesty, pylint: disable=import-error
    SiteConfiguration,
)
from pytz import UTC


class Command(BaseCommand):
    """
    Export all PDF course certificates with its links to a csv file and upload it to the
    `GRADES_DOWNLOAD` storage.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--certificate_download_domain",
            default="course-certificate.nau.edu.pt",
            help="The domain to use to download the certificates",
        )
        parser.add_argument("course_ids", nargs="*", metavar="course_id")

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

            course_key = CourseKey.from_string(course_id)
            lms_base = SiteConfiguration.get_value_for_org(
                course_key.org, "LMS_BASE", settings.LMS_BASE
            )

            # prepare output
            rows = []

            # append header
            rows.append(
                [
                    "course_id",
                    "student email",
                    "student name",
                    "certificate verify_uuid",
                    "certificate_web_link_url",
                    "certificate_download_pdf_link",
                ]
            )

            # iterate each certificate and append each certificate as a row
            for certificate in course_generated_certificates:
                certificate_web_link_url = (
                    "https://" + lms_base + "/certificates/" + certificate.verify_uuid
                )
                certificate_download_pdf_link = (
                    certificate_download_pdf_url + certificate.verify_uuid
                )

                rows.append(
                    [
                        course_id,
                        certificate.user.email,
                        certificate.name,
                        certificate.verify_uuid,
                        certificate_web_link_url,
                        certificate_download_pdf_link,
                    ]
                )

            upload_csv_to_report_store(
                rows,
                "export_course_certificates",
                course_key,
                start_date,
            )

            lms_instructor_data_download_url = (
                f"https://{lms_base}/courses/{course_id}/instructor#view-data_download"
            )
            self.log_msg(
                f"You can confirm the existence of the file on: {lms_instructor_data_download_url}"
            )
