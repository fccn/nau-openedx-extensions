"""
Tests for the SQL level write detection.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from nau_openedx_extensions.read_replica.state import request_state
from nau_openedx_extensions.read_replica.writes import WriteDetector, is_write


class IsWriteTest(SimpleTestCase):
    """
    Which statements make a request move to the writer.
    """

    def test_data_changing_statements_are_writes(self):
        """INSERT, UPDATE, DELETE and REPLACE are writes, whatever the case or the leading blanks."""
        for sql in (
            "INSERT INTO `student_user` (`a`) VALUES (%s)",
            "  update student_user set a = %s where id = %s",
            "\nDELETE FROM student_user WHERE id = %s",
            "REPLACE INTO student_user (`a`) VALUES (%s)",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(is_write(sql))

    def test_locking_reads_are_writes(self):
        """SELECT ... FOR UPDATE and FOR SHARE lock rows, so they belong on the writer."""
        for sql in (
            "SELECT `a`.`id` FROM `a` WHERE `a`.`id` = %s FOR UPDATE",
            "SELECT `a`.`id` FROM `a` WHERE `a`.`id` = %s FOR UPDATE NOWAIT",
            "SELECT `a`.`id` FROM `a` WHERE `a`.`id` = %s FOR SHARE SKIP LOCKED",
            "SELECT `a`.`id` FROM `a` WHERE `a`.`id` = %s LOCK IN SHARE MODE",
        ):
            with self.subTest(sql=sql):
                self.assertTrue(is_write(sql))

    def test_plain_reads_and_session_statements_are_not_writes(self):
        """Reads and the statements Django sends around a transaction do not move the request."""
        for sql in (
            "SELECT `a`.`id` FROM `a` WHERE `a`.`id` = %s",
            "SELECT 1",
            "SAVEPOINT `s1`",
            "RELEASE SAVEPOINT `s1`",
            "ROLLBACK TO SAVEPOINT `s1`",
            "SET autocommit=0",
            "SET SESSION wsrep_sync_wait = 1",
            "COMMIT",
        ):
            with self.subTest(sql=sql):
                self.assertFalse(is_write(sql))


class WriteDetectorTest(TestCase):
    """
    The execute wrapper, on the real database connection.
    """

    def setUp(self):
        super().setUp()
        request_state.reset()
        self.addCleanup(request_state.reset)

    def run_detector(self, sql):
        """
        Pass ``sql`` through a detector, and return what the wrapped call received.
        """
        received = []
        detector = WriteDetector(request_state)
        detector(lambda *args: received.append(args) or "result", sql, ("p",), False, {})
        return received

    def test_statement_is_executed_unchanged(self):
        """The wrapper never alters or swallows the statement."""
        self.assertEqual(self.run_detector("SELECT 1"), [("SELECT 1", ("p",), False, {})])
        self.assertFalse(request_state.wrote)

    def test_the_first_write_is_recorded_before_it_runs(self):
        """The flag is already set when the INSERT is executed, so nothing after it can read the replica."""
        seen = []
        detector = WriteDetector(request_state)
        detector(lambda *args: seen.append(request_state.wrote), "INSERT INTO a VALUES (1)", (), False, {})
        self.assertEqual(seen, [True])

    def test_get_or_create_of_an_existing_row_is_not_a_write(self):
        """
        The JWT authentication of the MFE APIs runs ``get_or_create`` for the user on every request. The router
        is asked for the writer, but no statement writes, so the request must stay on the replica.
        """
        user_model = get_user_model()
        user_model.objects.create(username="existing")
        from django.db import connections  # pylint: disable=import-outside-toplevel

        with connections["default"].execute_wrapper(WriteDetector(request_state)):
            user_model.objects.get_or_create(username="existing")
            self.assertFalse(request_state.wrote)
            user_model.objects.get_or_create(username="new-user")
            self.assertTrue(request_state.wrote)
