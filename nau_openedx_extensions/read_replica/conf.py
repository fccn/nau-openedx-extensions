"""
Settings of the read replica routing, with their defaults.

The values are plain Django settings so they can be set from the Tutor ``lms-env`` patch, like the other
``NAU_*`` settings of this plugin (see ``settings/production.py``). They are read on every call, never at import
time, so ``override_settings`` works in tests.
"""
import logging
import re
from functools import lru_cache

from django.conf import settings

log = logging.getLogger(__name__)

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


def routing_enabled():
    """
    Return whether the GET routing (router and middleware) is installed for this deployment.
    """
    return bool(getattr(settings, "NAU_READ_REPLICA_ROUTING_ENABLED", False))


def debug_header_enabled():
    """
    Return whether routed responses carry the ``X-NAU-DB-Route`` header, which tells where a request was served.
    """
    return bool(getattr(settings, "NAU_READ_REPLICA_DEBUG_HEADER", False))


@lru_cache(maxsize=8)
def _compile(patterns):
    """
    Compile the allow-list once per distinct list. A pattern that does not compile is logged and ignored: it must
    never turn into an error on every request.
    """
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error:
            log.error("Ignoring invalid NAU_READ_REPLICA_GET_ALLOWLIST pattern %r", pattern)
    return tuple(compiled)


def get_is_allowed(path):
    """
    Return whether ``path`` matches one of the ``NAU_READ_REPLICA_GET_ALLOWLIST`` patterns (matched from the start
    of the path, so patterns normally begin with ``^``). An empty list allows nothing.
    """
    patterns = tuple(getattr(settings, "NAU_READ_REPLICA_GET_ALLOWLIST", ()))
    return any(compiled.match(path) for compiled in _compile(patterns))


def barrier_slow_ms():
    """
    Return how long, in milliseconds, the causal barrier may take before the replica is considered to be lagging.

    On the lab the barrier took at most 14 ms when the replica only served reads and about 900 ms under flow control, so
    the default leaves room above the first and trips well before the one second timeout recommended for the replica.
    """
    return float(getattr(settings, "NAU_READ_REPLICA_BARRIER_SLOW_MS", 250))


def breaker_seconds():
    """
    Return for how many seconds a process skips the replica after the barrier failed or was slow.
    """
    return float(getattr(settings, "NAU_READ_REPLICA_BREAKER_SECONDS", 10))
