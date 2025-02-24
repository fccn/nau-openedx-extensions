"""
Send course certificates for Academia Portugal Digital.
"""
import hashlib
from datetime import datetime, timedelta

import requests  # lint-amnesty, pylint: disable=import-error
from common.djangoapps.util.query import use_read_replica_if_available  # lint-amnesty, pylint: disable=import-error
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from lms.djangoapps.certificates.models import GeneratedCertificate  # lint-amnesty, pylint: disable=import-error
from opaque_keys.edx.keys import CourseKey
from pytz import UTC


class Command(BaseCommand):
    """
    Send course certificates for Academia Portugal Digital.
    """

    API_URL = getattr(
        settings,
        "AMA_ACADEMIA_PORTUGAL_DIGITAL_API_URL",
        "https://academiaportugaldigital.pt/api/api/Course/FinishedIntegrationNau",
    )
    API_KEY = getattr(
        settings,
        "AMA_ACADEMIA_PORTUGAL_DIGITAL_API_KEY",
        None,
    )

    def add_arguments(self, parser):
        """
        Configure Django Command arguments
        """
        parser.add_argument(
            "--api_url",
            default=self.API_URL,
            help="URL to send course certificates",
        )
        parser.add_argument(
            "--api_key",
            default=self.API_KEY,
            help="API key to send course certificates",
        )
        parser.add_argument(
            "--days",
            default=7,
            help="Number of days course certificates will be sent out",
        )
        parser.add_argument(
            "--page_size",
            default=1000,
            help="Number of certificates to send in each request",
        )

    def log_msg(self, msg):
        """
        Log a message immediately
        """
        self.stdout.write(msg)
        self.stdout.flush()

    @staticmethod
    def generate_md5(value):
        """
        Generate MD5 hash
        """
        return hashlib.md5(value.encode()).hexdigest()

    def convert_certificates_to_academia_portugal_digital_format(self, certificates):
        """
        Convert certificates to Academia Portugal Digital format
        """
        return [
            {
                "key": self.generate_md5(certificate.user.email),
                "value": CourseKey.from_string(str(certificate.course_id)).course,
            }
            for certificate in certificates
        ]

    def send_certificates_to_academia_portugal_digital(self, api_url, api_key, certificates):
        """
        Send certificates to Academia Portugal Digital
        """
        completions = self.convert_certificates_to_academia_portugal_digital_format(
            certificates
        )
        self.log_msg(f"Sending certificates: {completions}")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            api_url,
            json=completions,
            headers=headers,
        )
        if response.ok:
            self.log_msg("Certificates sent successfully")
        else:
            self.log_msg(f"Failed to send certificates: {response.text}")

    def handle(self, *args, **options):
        """
        Execute the command
        """
        begin_date = datetime.now(UTC) - timedelta(days=options["days"])
        certificates_objects = use_read_replica_if_available(
            GeneratedCertificate.objects.filter(created_date__gte=begin_date)
            .order_by("created_date")
            .select_related("user")
        )
        paginator = Paginator(certificates_objects, options["page_size"])
        certificates_total_count = paginator.count
        certificates_count = 0
        for page_i in paginator.page_range:
            page = paginator.page(page_i)
            certificates = list(page.object_list)
            certificates_count += len(certificates)
            self.log_msg(
                f"Sending {certificates_count} of {certificates_total_count} certificates"
            )
            if certificates:
                api_key = options["api_key"]
                api_url = options["api_url"]
                self.send_certificates_to_academia_portugal_digital(api_url, api_key, certificates)
        self.log_msg("Finished sending certificates")
