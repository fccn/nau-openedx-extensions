"""
Celery tasks for certificate export functionality.

This module defines asynchronous tasks for exporting course certificates to a CSV file.
The tasks are designed to be executed in the background using Celery.

Tasks:
    - export_course_certificates_task: Exports course certificates as a CSV file
      and uploads it to the specified storage.

Dependencies:
    - Celery: Used for task management.
    - Command: The management command responsible for handling the certificate export logic.

Usage:
    The `export_course_certificates_task` can be triggered asynchronously to export certificates for a given course.
    Example:
        export_course_certificates_task.delay(course_id="course-v1:example+101+2025")
"""

from celery import shared_task

from nau_openedx_extensions.certificate_export.management.commands.export_course_certificates import Command


@shared_task
def export_course_certificates_task(course_id):
    """
    Celery task to export course certificates as a CSV file.
    """
    command = Command()
    options = {"course_ids": [course_id]}
    command.handle(**options)
