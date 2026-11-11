"""
Tests for the read replica routing of the heavy instructor reports.

``InstallConformanceTest`` is mandatory, not optional. The wrapper rebinds ``run_main_task`` inside an
edx-platform module we do not control and matches the tasks by the name they are registered with. If an upgrade
renames a task, adds a suffix, or stops resolving ``run_main_task`` from the tasks module, the routing silently
does nothing and the reports keep loading the writer. This suite makes that breakage surface during the upgrade.
"""
from types import SimpleNamespace
from unittest.mock import patch

from common.djangoapps.student.roles import CourseDataResearcherRole, CourseInstructorRole, CourseStaffRole
from common.djangoapps.student.tests.factories import UserFactory
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from edx_django_utils.db.read_replica import write_queries
from edx_toggles.toggles.testutils import override_waffle_switch
from lms.djangoapps.instructor_task import tasks
from lms.djangoapps.instructor_task.data import InstructorTaskTypes
from lms.djangoapps.instructor_task.models import InstructorTask
from opaque_keys.edx.locator import CourseLocator

from nau_openedx_extensions.read_replica import conf, reports, switches
from nau_openedx_extensions.read_replica.tests.helpers import replica_configured, routed_read_database

GRADES_TASK = "lms.djangoapps.instructor_task.tasks.calculate_grades_csv"
OTHER_TASK = "lms.djangoapps.instructor_task.tasks.cohort_students"
# The names the real tasks are registered with, so an upgrade that renames one cannot make the tests below vacuous.
PROBLEM_GRADE_TASK = tasks.calculate_problem_grade_report.name
PROBLEM_RESPONSES_TASK = tasks.calculate_problem_responses_csv.name
COURSE_KEY = CourseLocator("NAU", "REPORTS", "2026")
OTHER_COURSE_KEY = CourseLocator("NAU", "OTHER", "2026")


class ReportRoutingTest(TestCase):
    """
    Behaviour of the wrapper around ``run_main_task``.
    """

    def setUp(self):
        super().setUp()
        self.seen = {}
        self.calls = []

    def run_wrapped(self, task_name=GRADES_TASK, task_error=None, entry_id=7):
        """
        Run a fake ``run_main_task`` through the wrapper and record which database its two phases read from.
        """

        def task_fcn(*args, **kwargs):
            self.seen["task_fcn"] = routed_read_database()
            self.calls.append((args, kwargs))
            if task_error:
                raise task_error
            return "report"

        def run_main_task(entry_id, fcn, action_name):
            self.seen["bookkeeping"] = routed_read_database()
            return fcn(entry_id, "course", {}, action_name)

        current_task = SimpleNamespace(name=task_name) if task_name else None
        with replica_configured(), patch.object(reports, "current_task", current_task):
            wrapper = reports._wrap_run_main_task(run_main_task)  # pylint: disable=protected-access
            return wrapper(entry_id, task_fcn, "graded")

    def test_settings_default_off(self):
        """Nothing is routed unless a deployment turns the feature on."""
        self.assertFalse(conf.reports_enabled())
        self.assertIn(GRADES_TASK, conf.report_tasks())

    def test_nothing_is_routed_by_default(self):
        """With the defaults, the task function and the bookkeeping both read from the writer."""
        self.assertEqual(self.run_wrapped(), "report")
        self.assertEqual(self.seen, {"task_fcn": "default", "bookkeeping": "default"})

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_environment_setting_alone_is_not_enough(self):
        """The waffle switch is the run time gate: without it the report stays on the writer."""
        self.run_wrapped()
        self.assertEqual(self.seen["task_fcn"], "default")

    def test_waffle_switch_alone_is_not_enough(self):
        """The environment setting installs the feature: the switch alone does nothing."""
        with override_waffle_switch(switches.REPORTS, active=True):
            self.run_wrapped()
        self.assertEqual(self.seen["task_fcn"], "default")

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_only_the_task_function_runs_on_the_replica(self):
        """The heavy part reads from the replica, the InstructorTask bookkeeping stays on the writer."""
        with override_waffle_switch(switches.REPORTS, active=True):
            self.assertEqual(self.run_wrapped(), "report")
        self.assertEqual(self.seen, {"task_fcn": "read_replica", "bookkeeping": "default"})

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_arguments_are_passed_through(self):
        """The task function is called exactly as run_main_task calls it."""
        with override_waffle_switch(switches.REPORTS, active=True):
            self.run_wrapped()
        self.assertEqual(self.calls, [((7, "course", {}, "graded"), {})])

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_other_tasks_are_not_routed(self):
        """A task that is not in the list keeps the writer, whatever the switch says."""
        with override_waffle_switch(switches.REPORTS, active=True):
            self.run_wrapped(task_name=OTHER_TASK)
        self.assertEqual(self.seen["task_fcn"], "default")

    def test_the_problem_grade_report_is_not_in_the_default_list(self):
        """
        The problem grade report writes while it builds the course blocks of each learner (cohort assignment,
        library content selection, grade recalculation) and reads those rows back, so it is not routed.
        """
        self.assertNotIn(PROBLEM_GRADE_TASK, conf.DEFAULT_REPORT_TASKS)
        self.assertNotIn(PROBLEM_GRADE_TASK, conf.report_tasks())

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_the_problem_grade_report_reads_from_the_writer(self):
        """With both gates open it still reads from the writer, so it sees the rows it has just written."""
        with override_waffle_switch(switches.REPORTS, active=True):
            self.run_wrapped(task_name=PROBLEM_GRADE_TASK)
        self.assertEqual(self.seen["task_fcn"], "default")

    def request_by(self, requester):
        """
        Return the id of an ``InstructorTask`` row of the course, requested by ``requester``.
        """
        return InstructorTask.create(COURSE_KEY, InstructorTaskTypes.PROBLEM_RESPONSES_CSV, "", {}, requester).id

    def run_with_gates_open(self, entry_id, task_name=PROBLEM_RESPONSES_TASK):
        """
        Run the task with the environment setting and the switch on and return where its task function read from.
        """
        with override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True):
            with override_waffle_switch(switches.REPORTS, active=True):
                self.run_wrapped(task_name=task_name, entry_id=entry_id)
        return self.seen["task_fcn"]

    def test_a_requester_with_staff_access_gets_the_report_from_the_replica(self):
        """The user partition transformer skips the group checks for staff, so nothing is written."""
        course_staff = UserFactory()
        CourseStaffRole(COURSE_KEY).add_users(course_staff)
        instructor = UserFactory()
        CourseInstructorRole(COURSE_KEY).add_users(instructor)
        requesters = {
            "course staff": course_staff,
            "instructor": instructor,
            "global staff": UserFactory(is_staff=True),
        }
        for kind, requester in requesters.items():
            with self.subTest(requester=kind):
                self.assertEqual(self.run_with_gates_open(self.request_by(requester)), "read_replica")

    def test_a_requester_without_staff_access_gets_the_report_from_the_writer(self):
        """
        For any other requester the transformer can assign the requester to the default cohort, a write that the
        report reads back, so the report stays on the writer.
        """
        data_researcher = UserFactory()
        CourseDataResearcherRole(COURSE_KEY).add_users(data_researcher)
        staff_of_another_course = UserFactory()
        CourseStaffRole(OTHER_COURSE_KEY).add_users(staff_of_another_course)
        requesters = {
            "learner": UserFactory(),
            "data researcher": data_researcher,
            "staff of another course": staff_of_another_course,
        }
        for kind, requester in requesters.items():
            with self.subTest(requester=kind):
                self.assertEqual(self.run_with_gates_open(self.request_by(requester)), "default")

    def test_the_staff_access_is_checked_on_the_writer(self):
        """The requester is checked before the task function is routed, so a lagging replica cannot answer."""
        seen = []

        def has_access(user, action, course_key):
            seen.append((routed_read_database(), user.pk, action, course_key))
            return True

        requester = UserFactory()
        with patch("lms.djangoapps.courseware.access.has_access", side_effect=has_access):
            self.assertEqual(self.run_with_gates_open(self.request_by(requester)), "read_replica")
        self.assertEqual(seen, [("default", requester.pk, "staff", COURSE_KEY)])

    def test_a_requester_that_cannot_be_checked_gets_the_report_from_the_writer(self):
        """A failure of the check never fails the report: it stays on the writer and a warning is logged."""
        entry_id = self.request_by(UserFactory())
        with self.subTest(failure="unknown instructor task"), self.assertLogs(reports.log, "WARNING"):
            self.assertEqual(self.run_with_gates_open(entry_id=entry_id + 1), "default")
        with self.subTest(failure="access check error"), self.assertLogs(reports.log, "WARNING"):
            with patch("lms.djangoapps.courseware.access.has_access", side_effect=RuntimeError("boom")):
                self.assertEqual(self.run_with_gates_open(entry_id), "default")

    def test_only_a_routed_staff_only_task_looks_up_its_requester(self):
        """A task that does not depend on its requester, or that is not routed at all, pays no query for it."""
        entry_id = self.request_by(UserFactory())
        cases = (
            ("task that does not depend on its requester", GRADES_TASK, True, False),
            ("switch off", PROBLEM_RESPONSES_TASK, False, False),
            ("both gates open", PROBLEM_RESPONSES_TASK, True, True),
        )
        for case, task_name, switch_on, looks_up_the_requester in cases:
            with self.subTest(case=case), override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True):
                with override_waffle_switch(switches.REPORTS, active=switch_on):
                    with CaptureQueriesContext(connection) as queries:
                        self.run_wrapped(task_name=task_name, entry_id=entry_id)
                statements = [query["sql"] for query in queries.captured_queries]
                lookups = [sql for sql in statements if "instructor_task_instructortask" in sql]
                self.assertEqual(bool(lookups), looks_up_the_requester)

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_outside_a_task_nothing_is_routed(self):
        """run_main_task called without a Celery task (a shell, a test) is never routed."""
        with override_waffle_switch(switches.REPORTS, active=True):
            self.run_wrapped(task_name=None)
        self.assertEqual(self.seen["task_fcn"], "default")

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True, NAU_READ_REPLICA_REPORT_TASKS=[OTHER_TASK])
    def test_task_list_is_configurable(self):
        """The list of routed tasks comes from the settings."""
        with override_waffle_switch(switches.REPORTS, active=True):
            self.run_wrapped(task_name=GRADES_TASK)
            self.assertEqual(self.seen["task_fcn"], "default")
            self.run_wrapped(task_name=OTHER_TASK)
            self.assertEqual(self.seen["task_fcn"], "read_replica")

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_routing_is_released_after_the_task(self):
        """The replica routing never leaks past the task, not even when the task fails."""
        with override_waffle_switch(switches.REPORTS, active=True):
            self.run_wrapped()
            self.assertEqual(routed_read_database(), "default")
            with self.assertRaises(ValueError):
                self.run_wrapped(task_error=ValueError("boom"))
            self.assertEqual(routed_read_database(), "default")

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_inside_write_queries_the_task_runs_on_the_writer(self):
        """read_queries_only() cannot be entered inside write_queries(): the report must still run."""
        with override_waffle_switch(switches.REPORTS, active=True), write_queries():
            self.assertEqual(self.run_wrapped(), "report")
        self.assertEqual(self.seen["task_fcn"], "default")

    @override_settings(NAU_READ_REPLICA_REPORTS_ENABLED=True)
    def test_an_assertion_error_of_the_report_is_not_swallowed(self):
        """Only entering the routing is protected: a failing report is neither hidden nor run twice."""
        with override_waffle_switch(switches.REPORTS, active=True):
            with self.assertRaises(AssertionError):
                self.run_wrapped(task_error=AssertionError("report bug"))
        self.assertEqual(len(self.calls), 1)

    def test_wrapping_twice_does_not_stack_wrappers(self):
        """install() is safe to call again."""
        wrapped = reports._wrap_run_main_task(lambda *args: None)  # pylint: disable=protected-access
        self.assertIs(reports._wrap_run_main_task(wrapped), wrapped)  # pylint: disable=protected-access


class InstallConformanceTest(TestCase):
    """
    The assumptions the routing makes about edx-platform.
    """

    TASK_ATTRIBUTES = (
        "calculate_grades_csv",
        "calculate_problem_responses_csv",
        "calculate_students_features_csv",
        "calculate_may_enroll_csv",
        "course_survey_report_csv",
    )

    def test_run_main_task_is_wrapped_in_the_tasks_module(self):
        """AppConfig.ready() already installed the wrapper where the tasks look it up."""
        self.assertTrue(getattr(tasks.run_main_task, "_nau_read_replica", False))

    def test_install_is_idempotent(self):
        """Calling install() again must not wrap the wrapper."""
        before = tasks.run_main_task
        reports.install()
        self.assertIs(tasks.run_main_task, before)

    def test_default_task_names_are_the_registered_names(self):
        """The default list holds the names the tasks are registered with, including the .v2 suffix."""
        registered = {getattr(tasks, attribute).name for attribute in self.TASK_ATTRIBUTES}
        self.assertEqual(registered, set(conf.DEFAULT_REPORT_TASKS))

    def test_staff_only_task_names_are_the_registered_names(self):
        """The staff only list holds the registered name of the problem responses task, which is a routed task."""
        self.assertEqual(conf.STAFF_ONLY_REPORT_TASKS, {PROBLEM_RESPONSES_TASK})
        self.assertLessEqual(conf.STAFF_ONLY_REPORT_TASKS, set(conf.DEFAULT_REPORT_TASKS))

    def test_report_tasks_resolve_run_main_task_from_the_tasks_module(self):
        """
        Every routed task calls ``run_main_task(entry_id, task_fn, action_name)`` through the tasks module
        namespace, so the rebinding is seen, and passes a callable as the task function.
        """
        for attribute in self.TASK_ATTRIBUTES:
            with self.subTest(task=attribute), patch.object(tasks, "run_main_task") as run_main_task:
                getattr(tasks, attribute).run(1, {})
                run_main_task.assert_called_once()
                entry_id, task_fn, action_name = run_main_task.call_args[0]
                self.assertEqual(entry_id, 1)
                self.assertTrue(callable(task_fn))
                self.assertTrue(action_name)
