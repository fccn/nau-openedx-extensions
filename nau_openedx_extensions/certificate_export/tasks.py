from celery import shared_task
from nau_openedx_extensions.management.commands.export_course_certificates import Command

@shared_task
def export_course_certificates_task(course_id, certificate_download_domain="course-certificate.nau.edu.pt"):
    """
    Celery task to export course certificates as a CSV file.
    """
    command = Command()
    options = {
        "certificate_download_domain": certificate_download_domain,
        "course_ids": [course_id],
    }
    command.handle(**options)