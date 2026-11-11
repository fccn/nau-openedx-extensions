"""
Settings of the read replica routing, with their defaults.

The values are plain Django settings so they can be set from the Tutor ``lms-env`` patch, like the other
``NAU_*`` settings of this plugin (see ``settings/production.py``). They are read on every call, never at import
time, so ``override_settings`` works in tests.
"""
from django.conf import settings

# The instructor tasks whose queries are served by the read replica. They are report generators that only read: each
# was audited for writes and run with every SQL statement recorded, and apart from the InstructorTask bookkeeping
# row, which stays on the writer, none of them writes for a requester with staff access (see
# ``STAFF_ONLY_REPORT_TASKS``). A snapshot that is a few milliseconds behind the writer is fine for a report. The
# names are the ones the tasks are registered with, which is what ``celery.current_task.name`` returns, so
# ``calculate_problem_responses_csv`` carries its ``.v2`` suffix.
#
# Tasks that write (grading, certificates, cohorts, bulk e-mail) must never be listed. The problem grade report
# writes whoever requests it, so it is deliberately not listed: for every learner it builds the course blocks, and
# the block transformers save the learner's library content selection and assign a learner without a cohort to
# one, creating the default cohort and recalculating the learner's grades. The task reads those rows back, and a
# replica that lags does not have them yet. The ORA2 exports are not listed either: their queries live in the
# edx-ora2 package and have not been measured.
DEFAULT_REPORT_TASKS = (
    "lms.djangoapps.instructor_task.tasks.calculate_grades_csv",
    "lms.djangoapps.instructor_task.tasks.calculate_problem_responses_csv.v2",
    "lms.djangoapps.instructor_task.tasks.calculate_students_features_csv",
    "lms.djangoapps.instructor_task.tasks.calculate_may_enroll_csv",
    "lms.djangoapps.instructor_task.tasks.course_survey_report_csv",
)

# The routed tasks that only read when their requester has staff access to the course. The problem responses report
# builds the course blocks for its requester. The user partition transformer skips the group checks for staff, but
# for any other requester, a data researcher for example, in a course whose content groups use the cohort scheme, it
# assigns the requester to a cohort, creating the default cohort if the course has none. The report then reads that
# cohort back, and a replica that lags does not have it yet, so the report fails.
STAFF_ONLY_REPORT_TASKS = frozenset({"lms.djangoapps.instructor_task.tasks.calculate_problem_responses_csv.v2"})


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
