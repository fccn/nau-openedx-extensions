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


def submit_calculate_problem_responses_csv(*args, **kwargs):
    """
    Wrapper for `lms.djangoapps.instructor_task.api.submit_calculate_problem_responses_csv` in edx-platform.
    Submits a task to generate the problem responses CSV report (student_state_from_block).
    """
    backend_function = settings.NAU_INSTRUCTOR_TASK_MODULE
    backend = import_module(backend_function)
    return backend.submit_calculate_problem_responses_csv(*args, **kwargs)


def get_report_store(*args, **kwargs):
    """
    Wrapper for `lms.djangoapps.instructor_task.models.ReportStore.from_config` in edx-platform.
    Returns a ReportStore instance that can be used to list and access report files.
    """
    backend_function = settings.NAU_INSTRUCTOR_TASK_MODULE
    backend = import_module(backend_function)
    return backend.ReportStore.from_config(*args, **kwargs)
