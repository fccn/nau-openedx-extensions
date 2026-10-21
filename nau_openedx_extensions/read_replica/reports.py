"""
Run the heavy instructor reports on the read replica.

The grade report, the problem grade report, the problem responses report and the CSV listings scan every learner
of a course for minutes, on the writer, next to the learners. They only read, so they can use the replica.

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


def _routes_to_replica(task_name):
    """
    Return whether the task called ``task_name`` should run its queries on the replica.

    The cheap checks come first, the switch is read last because it can touch the cache and the database.
    """
    return bool(conf.reports_enabled() and task_name in conf.report_tasks() and REPORTS.is_enabled())


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
        if _routes_to_replica(task_name):
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
