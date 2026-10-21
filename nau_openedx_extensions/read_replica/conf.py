"""
Settings of the read replica routing, with their defaults.

The values are plain Django settings so they can be set from the Tutor ``lms-env`` patch, like the other
``NAU_*`` settings of this plugin (see ``settings/production.py``). They are read on every call, never at import
time, so ``override_settings`` works in tests.
"""
from django.conf import settings

# The instructor tasks whose queries are served by the read replica. They are report generators: they only read,
# and a snapshot that is a few milliseconds behind the writer is fine for a report. The names are the ones the
# tasks are registered with, which is what ``celery.current_task.name`` returns, so
# ``calculate_problem_responses_csv`` carries its ``.v2`` suffix. Tasks that write (grading, certificates,
# cohorts, bulk e-mail) must never be listed. The ORA2 exports are not listed because their queries live in the
# edx-ora2 package and were not audited.
DEFAULT_REPORT_TASKS = (
    "lms.djangoapps.instructor_task.tasks.calculate_grades_csv",
    "lms.djangoapps.instructor_task.tasks.calculate_problem_grade_report",
    "lms.djangoapps.instructor_task.tasks.calculate_problem_responses_csv.v2",
    "lms.djangoapps.instructor_task.tasks.calculate_students_features_csv",
    "lms.djangoapps.instructor_task.tasks.calculate_may_enroll_csv",
    "lms.djangoapps.instructor_task.tasks.course_survey_report_csv",
)


def reports_enabled():
    """
    Return whether the report routing is installed for this deployment.
    """
    return bool(getattr(settings, "NAU_READ_REPLICA_REPORTS_ENABLED", False))


def report_tasks():
    """
    Return the registered names of the instructor tasks that run on the read replica.
    """
    return frozenset(getattr(settings, "NAU_READ_REPLICA_REPORT_TASKS", DEFAULT_REPORT_TASKS))
