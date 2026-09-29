"""
Celery tasks for survey export functionality.

Main tasks:

    - export_course_surveys_task: Exports the responses of every Survey component of a course
      as one CSV file and uploads it to the report store.

Dependencies:
    - Celery: Used for task management.
    - Command: The ``export_course_surveys`` management command that builds the survey report.
"""

from celery import shared_task

from nau_openedx_extensions.management.commands.export_course_surveys import Command


@shared_task
def export_course_surveys_task(course_id):
    """
    Celery task to export the responses of every Survey component of a course as a CSV file.
    """
    command = Command()
    options = {"course_ids": [course_id]}
    command.handle(**options)
