"""
Run the heavy instructor reports on the read replica.

The grade report, the problem responses report and the CSV listings scan every learner of a course for minutes, on
the writer, next to the learners. They only read, so they can use the replica. The problem grade report is not one
of them: it writes while it builds the course blocks of each learner (see ``conf.DEFAULT_REPORT_TASKS``). The
problem responses report builds the course blocks for its requester, so it is routed only when the requester has
staff access (see ``conf.STAFF_ONLY_REPORT_TASKS``).

``run_main_task`` is the one function every instructor task goes through. It loads the ``InstructorTask`` row, hands
the real work to ``task_fcn`` and, later, ``BaseInstructorTask.on_success`` / ``on_failure`` load the row again
and save it. Those reads must see the row as the writer has it, because ``save()`` writes the whole row back. So
the wrapper below routes only ``task_fcn``, the heavy part, and leaves the bookkeeping on the writer.

This is a monkeypatch, because ``instructor_task`` exposes no hook. It is installed once from
``AppConfig.ready()`` and stays inert unless ``NAU_READ_REPLICA_REPORTS_ENABLED`` is true and the
``nau_read_replica.reports`` waffle switch is active. ``tests/test_reports.py`` is the conformance test that
detects silent breakage on upstream refactors.
"""
import logging
from functools import wraps

from celery import current_task

from nau_openedx_extensions.read_replica import conf
from nau_openedx_extensions.read_replica.context import replica_reads
from nau_openedx_extensions.read_replica.switches import REPORTS

log = logging.getLogger(__name__)


def _current_task_name():
    """
    Return the registered name of the Celery task that is running, if any.
    """
    return getattr(current_task, "name", None)


def _requester_has_staff_access(entry_id):
    """
    Return whether the user who requested the instructor task ``entry_id`` has staff access to its course.

    The task is not routed yet when this runs, so the ``InstructorTask`` row and the access roles are read from the
    writer. If the answer cannot be found, it is no and the report stays on the writer.
    """
    try:
        # pylint: disable=import-error,import-outside-toplevel
        from lms.djangoapps.courseware.access import has_access
        from lms.djangoapps.instructor_task.models import InstructorTask

        entry = InstructorTask.objects.select_related("requester").get(pk=entry_id)
        return bool(has_access(entry.requester, "staff", entry.course_id))
    except Exception:  # pylint: disable=broad-except
        log.warning(
            "Cannot tell whether the requester of instructor task %s has staff access, using the writer.",
            entry_id,
            exc_info=True,
        )
        return False


def _routes_to_replica(task_name, entry_id):
    """
    Return whether the task called ``task_name``, stored in the ``InstructorTask`` row ``entry_id``, should run its
    queries on the replica.

    The cheap checks come first and the switch is read last of them, because it can touch the cache and the
    database. The requester is looked up after the gates and only for the ``STAFF_ONLY_REPORT_TASKS``, so no other
    task pays for an extra query.
    """
    if not (conf.reports_enabled() and task_name in conf.report_tasks() and REPORTS.is_enabled()):
        return False
    return task_name not in conf.STAFF_ONLY_REPORT_TASKS or _requester_has_staff_access(entry_id)


def _on_replica(task_fcn, task_name):
    """
    Return ``task_fcn`` wrapped so that its reads go to the read replica.
    """

    @wraps(task_fcn)
    def wrapper(*args, **kwargs):
        log.info("Task %s runs its queries on the read replica.", task_name)
        with replica_reads():
            return task_fcn(*args, **kwargs)

    return wrapper


def _wrap_run_main_task(run_main_task):
    """
    Wrap ``run_main_task`` so the task function of the configured report tasks reads from the replica.
    """
    if getattr(run_main_task, "_nau_read_replica", False):
        return run_main_task

    @wraps(run_main_task)
    def wrapper(entry_id, task_fcn, action_name):
        task_name = _current_task_name()
        if _routes_to_replica(task_name, entry_id):
            task_fcn = _on_replica(task_fcn, task_name)
        return run_main_task(entry_id, task_fcn, action_name)

    wrapper._nau_read_replica = True  # pylint: disable=protected-access
    return wrapper


def install():
    """
    Rebind ``run_main_task`` in the instructor tasks module to the wrapping version.

    Called once from ``AppConfig.ready()``; safe to call again (an already wrapped function is left untouched).
    ``tasks.py`` looks the name up in its own namespace every time a task runs, so rebinding it there is enough.
    """
    # pylint: disable=import-error,import-outside-toplevel
    from lms.djangoapps.instructor_task import tasks

    tasks.run_main_task = _wrap_run_main_task(tasks.run_main_task)
    log.info("Read replica routing of instructor reports installed (enabled=%s)", conf.reports_enabled())
