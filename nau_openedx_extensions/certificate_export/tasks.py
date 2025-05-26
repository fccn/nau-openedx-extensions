"""
Celery tasks for certificate export functionality.
"""
import logging
from celery import task
from django.core.management import call_command

log = logging.getLogger(__name__)

@task(name='nau_openedx_extensions.certificate_export.tasks.export_csv')
def export_course_certificates_csv_task(course_id):
    """
    Run the export_course_certificates management command asynchronously.

    Args:
        course_id (str): The course ID to export certificates for.
    """
    log.info(f"Starting certificate CSV export for course {course_id}")
    try:
        call_command('export_course_certificates', course_id)
        log.info(f"Certificate CSV export completed for course {course_id}")
        return True
    except Exception as e:
        log.error(f"Error exporting certificates CSV for course {course_id}: {str(e)}")
        raise