"""
Instructor task backend abstraction.
"""

from importlib import import_module

from django.conf import settings


def upload_zip_to_report_store(*args, **kwargs):
    """
    Wrapper for `lms.djangoapps.instructor_task.tasks_helper.utils.upload_zip_to_report_store` in edx-platform.
    """
    backend_function = settings.NAU_INSTRUCTOR_TASK_MODULE
    backend = import_module(backend_function)
    return backend.upload_zip_to_report_store(*args, **kwargs)


def upload_csv_to_report_store(*args, **kwargs):
    """
    Wrapper for `lms.djangoapps.instructor_task.tasks_helper.utils.upload_csv_to_report_store` in edx-platform.
    """
    backend_function = settings.NAU_INSTRUCTOR_TASK_MODULE
    backend = import_module(backend_function)
    return backend.upload_csv_to_report_store(*args, **kwargs)
