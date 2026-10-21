"""
Tests for the middleware that serves allow-listed GET requests from the read replica.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import OperationalError, connections
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.utils.connection import ConnectionDoesNotExist
from edx_toggles.toggles.testutils import override_waffle_switch

from nau_openedx_extensions.read_replica import middleware, switches
from nau_openedx_extensions.read_replica.breaker import CircuitBreaker, replica_breaker
from nau_openedx_extensions.read_replica.registration import NAU_ROUTER
from nau_openedx_extensions.read_replica.state import request_state
from nau_openedx_extensions.read_replica.tests.helpers import replica_configured, routed_read_database

ALLOWED = "/api/course_home/outline/course-v1:A+B+C"
ROUTING_ON = {
    "NAU_READ_REPLICA_ROUTING_ENABLED": True,
    "NAU_READ_REPLICA_GET_ALLOWLIST": [r"^/api/course_home/outline/"],
    "NAU_READ_REPLICA_DEBUG_HEADER": True,
    # The real router of the deployment, so a write moves the request back to the writer.
    "DATABASE_ROUTERS": [NAU_ROUTER],
}


class MiddlewareTestCase(TestCase):
    """
    Common setup: a middleware around a view that records where its reads would go.
    """

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        self.reads = []
        self.view_writes = False
        self.barrier = patch.object(middleware, "_causal_barrier", return_value=0.001).start()
        self.addCleanup(patch.stopall)
        request_state.reset()
        self.addCleanup(request_state.reset)
        replica_breaker.reset()
        self.addCleanup(replica_breaker.reset)

    def view(self, request):  # pylint: disable=unused-argument
        """
        A view that reads once, and then, if asked to, writes and reads again.
        """
        self.reads.append(routed_read_database())
        if self.view_writes:
            get_user_model().objects.create(username="written-by-the-view")
            self.reads.append(routed_read_database())
        return HttpResponse("ok")

    def serve(self, path=ALLOWED, method="GET"):
        """
        Serve a request through the middleware, with the replica configured and the switch on.
        """
        request = self.factory.generic(method, path)
        with replica_configured(), override_waffle_switch(switches.GET_ROUTING, active=True):
            return middleware.NauReadReplicaMiddleware(self.view)(request)


@override_settings(**ROUTING_ON)
class RoutedRequestTest(MiddlewareTestCase):
    """
    A request that matches the allow-list while everything is on.
    """

    def test_reads_go_to_the_replica_after_the_barrier(self):
        """The barrier runs once, before the view, and the view reads from the replica."""
        order = []
        self.barrier.side_effect = lambda: order.append("barrier") or 0.001
        original_view = self.view
        self.view = lambda request: order.append("view") or original_view(request)
        response = self.serve()
        self.assertEqual(order, ["barrier", "view"])
        self.assertEqual(self.reads, ["read_replica"])
        self.assertEqual(response["X-NAU-DB-Route"], "replica")

    def test_head_requests_are_routed_too(self):
        """HEAD is as safe as GET."""
        self.serve(method="HEAD")
        self.assertEqual(self.reads, ["read_replica"])

    def test_the_first_write_sends_the_rest_of_the_request_to_the_writer(self):
        """After a real INSERT the view reads from the writer, so it sees what it just wrote."""
        self.view_writes = True
        response = self.serve()
        self.assertEqual(self.reads, ["read_replica", "default"])
        self.assertEqual(response["X-NAU-DB-Route"], "writer")

    def test_get_or_create_of_an_existing_user_keeps_the_request_on_the_replica(self):
        """
        The JWT authentication runs ``get_or_create`` for the user on every MFE request. It asks the router for
        the writer but writes nothing, so it must not take the request off the replica.
        """
        get_user_model().objects.create(username="learner")
        original_view = self.view

        def view(request):
            get_user_model().objects.get_or_create(username="learner")
            return original_view(request)

        self.view = view
        response = self.serve()
        self.assertEqual(self.reads, ["read_replica"])
        self.assertEqual(response["X-NAU-DB-Route"], "replica")

    def test_the_state_and_the_routing_are_released_after_the_request(self):
        """Nothing leaks into the next request of the same thread."""
        self.serve()
        self.assertEqual(routed_read_database(), "default")
        self.assertFalse(request_state.active)
        self.assertEqual(connections["default"].execute_wrappers, [])

    def test_the_state_is_released_when_the_view_fails(self):
        """A view that raises still releases the routing and the write detector."""

        def view(request):
            raise ValueError("boom")

        self.view = view
        with self.assertRaises(ValueError):
            self.serve()
        self.assertFalse(request_state.active)
        self.assertEqual(connections["default"].execute_wrappers, [])
        self.assertEqual(routed_read_database(), "default")

    def test_the_view_sees_the_request_path_in_the_state(self):
        """The router can say which endpoint did a read-modify-write."""
        seen = []
        self.view = lambda request: seen.append(request_state.path) or HttpResponse("ok")
        self.serve()
        self.assertEqual(seen, [ALLOWED])


@override_settings(**ROUTING_ON)
class BarrierFailureTest(MiddlewareTestCase):
    """
    The replica cannot be used: the request is still served, by the writer.
    """

    def test_a_failing_barrier_falls_back_to_the_writer(self):
        """A timeout or a connection error never fails the request."""
        self.barrier.side_effect = OperationalError(1205, "causality wait timed out")
        with self.assertLogs("nau_openedx_extensions.read_replica.middleware", level="WARNING") as logs:
            response = self.serve()
        self.assertEqual(self.reads, ["default"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-NAU-DB-Route"], "writer")
        self.assertIn("causal barrier", logs.output[0])

    def test_a_missing_replica_alias_falls_back_to_the_writer(self):
        """An environment without a replica keeps working."""
        self.barrier.side_effect = ConnectionDoesNotExist("The connection 'read_replica' doesn't exist.")
        with self.assertLogs("nau_openedx_extensions.read_replica.middleware", level="WARNING"):
            self.serve()
        self.assertEqual(self.reads, ["default"])

    def test_other_errors_are_not_hidden(self):
        """Only database errors are handled: a bug in the barrier is not silenced."""
        self.barrier.side_effect = KeyError("bug")
        with self.assertRaises(KeyError):
            self.serve()


@override_settings(**ROUTING_ON)
class CircuitBreakerTest(MiddlewareTestCase):
    """
    A replica that lags must not make every request wait for it.
    """

    def test_a_failing_barrier_opens_the_breaker(self):
        """After a failure the next requests skip the replica, and do not even run the barrier."""
        self.barrier.side_effect = OperationalError(1205, "causality wait timed out")
        with self.assertLogs("nau_openedx_extensions.read_replica.middleware", level="WARNING"):
            self.serve()
        self.assertTrue(replica_breaker.is_open())

        self.barrier.reset_mock()
        self.barrier.side_effect = None
        response = self.serve()
        self.barrier.assert_not_called()
        self.assertEqual(self.reads, ["default", "default"])
        self.assertEqual(response["X-NAU-DB-Route"], "writer")

    def test_a_slow_barrier_still_serves_this_request_from_the_replica_and_opens_the_breaker(self):
        """The slow request is consistent, so it is routed. The ones after it skip the replica."""
        self.barrier.return_value = 0.9
        with self.assertLogs("nau_openedx_extensions.read_replica.middleware", level="WARNING") as logs:
            first = self.serve()
        self.assertEqual(self.reads, ["read_replica"])
        self.assertEqual(first["X-NAU-DB-Route"], "replica")
        self.assertIn("900 ms", logs.output[0])

        second = self.serve()
        self.assertEqual(self.reads, ["read_replica", "default"])
        self.assertEqual(second["X-NAU-DB-Route"], "writer")
        self.assertEqual(self.barrier.call_count, 1)

    def test_a_barrier_under_the_threshold_keeps_the_breaker_closed(self):
        """A normal barrier never trips anything."""
        self.barrier.return_value = 0.02
        self.serve()
        self.serve()
        self.assertFalse(replica_breaker.is_open())
        self.assertEqual(self.reads, ["read_replica", "read_replica"])

    @override_settings(NAU_READ_REPLICA_BARRIER_SLOW_MS=5, NAU_READ_REPLICA_BREAKER_SECONDS=30)
    def test_the_threshold_and_the_window_are_settings(self):
        """Both numbers come from the settings."""
        clock = [100.0]
        breaker = CircuitBreaker(clock=lambda: clock[0])
        self.barrier.return_value = 0.01
        with patch.object(middleware, "replica_breaker", breaker), self.assertLogs(
            "nau_openedx_extensions.read_replica.middleware", level="WARNING"
        ):
            self.serve()
            self.assertTrue(breaker.is_open())
            clock[0] += 29
            self.assertTrue(breaker.is_open())
            clock[0] += 2
            self.assertFalse(breaker.is_open())

    def test_the_replica_is_used_again_when_the_window_is_over(self):
        """The breaker closes by itself, so a recovered replica is used again without a restart."""
        clock = [100.0]
        breaker = CircuitBreaker(clock=lambda: clock[0])
        breaker.trip(10)
        with patch.object(middleware, "replica_breaker", breaker):
            self.serve()
            self.assertEqual(self.reads, ["default"])
            clock[0] += 11
            self.serve()
        self.assertEqual(self.reads, ["default", "read_replica"])


class NotRoutedTest(MiddlewareTestCase):
    """
    Requests that must keep the writer, and cost nothing: no barrier, no header.
    """

    def assert_not_routed(self, **serve_args):
        """
        Serve a request and check that it went through untouched.
        """
        response = self.serve(**serve_args)
        self.assertEqual(self.reads, ["default"])
        self.barrier.assert_not_called()
        self.assertNotIn("X-NAU-DB-Route", response)

    def test_nothing_is_routed_by_default(self):
        """With the defaults the middleware is a pass through."""
        self.assert_not_routed()

    @override_settings(**ROUTING_ON)
    def test_writes_are_never_routed(self):
        """Only GET and HEAD are candidates, even on an allow-listed path."""
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.reads.clear()
                self.assert_not_routed(method=method)

    @override_settings(**ROUTING_ON)
    def test_paths_outside_the_allow_list_are_not_routed(self):
        """Only the listed endpoints are routed."""
        self.assert_not_routed(path="/api/courseware/sequence/block-v1:A+B+C+type@sequential+block@x")

    @override_settings(**{**ROUTING_ON, "NAU_READ_REPLICA_GET_ALLOWLIST": []})
    def test_an_empty_allow_list_routes_nothing(self):
        """Installing the routing without an allow-list changes nothing."""
        self.assert_not_routed()

    @override_settings(**{**ROUTING_ON, "NAU_READ_REPLICA_ROUTING_ENABLED": False})
    def test_the_environment_setting_is_required(self):
        """The environment setting is the install gate."""
        self.assert_not_routed()

    @override_settings(**ROUTING_ON)
    def test_the_waffle_switch_is_required(self):
        """The switch is the run time gate: without it, nothing is routed."""
        request = self.factory.get(ALLOWED)
        with replica_configured(), override_waffle_switch(switches.GET_ROUTING, active=False):
            response = middleware.NauReadReplicaMiddleware(self.view)(request)
        self.assertEqual(self.reads, ["default"])
        self.barrier.assert_not_called()
        self.assertNotIn("X-NAU-DB-Route", response)


@override_settings(**{**ROUTING_ON, "NAU_READ_REPLICA_DEBUG_HEADER": False})
class DebugHeaderTest(MiddlewareTestCase):
    """
    The header is only for validation.
    """

    def test_there_is_no_header_unless_it_is_turned_on(self):
        """Production responses do not say anything about the database."""
        response = self.serve()
        self.assertEqual(self.reads, ["read_replica"])
        self.assertNotIn("X-NAU-DB-Route", response)


class CausalBarrierTest(TestCase):
    """
    The statements the barrier sends.
    """

    waited = None

    def run_barrier(self, fail_on=None):
        """
        Run the barrier against a fake connection and return the statements it executed.
        """
        statements = []

        class Cursor:  # pylint: disable=missing-class-docstring
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql):  # pylint: disable=missing-function-docstring
                statements.append(sql)
                if sql == fail_on:
                    raise OperationalError(1205, "timeout")

        class Connection:  # pylint: disable=missing-class-docstring
            closed = False

            def ensure_connection(self):  # pylint: disable=missing-function-docstring
                statements.append("connect")

            def cursor(self):  # pylint: disable=missing-function-docstring
                return Cursor()

            def close(self):  # pylint: disable=missing-function-docstring
                self.closed = True

        connection = Connection()
        waited = None
        with patch.object(middleware, "connections", {"read_replica": connection}):
            try:
                waited = middleware._causal_barrier()  # pylint: disable=protected-access
            except OperationalError:
                pass
        self.waited = waited
        return statements, connection

    def test_the_wait_is_on_only_around_the_barrier_statement(self):
        """The rest of the request must not pay the wait for every query."""
        statements, connection = self.run_barrier()
        self.assertEqual(
            statements, ["connect", "SET SESSION wsrep_sync_wait = 1", "SELECT 1", "SET SESSION wsrep_sync_wait = 0"]
        )
        self.assertFalse(connection.closed)

    def test_it_returns_the_time_the_wait_took(self):
        """The latency that feeds the circuit breaker, in seconds, measured after the connection is made."""
        self.run_barrier()
        self.assertIsInstance(self.waited, float)
        self.assertGreaterEqual(self.waited, 0)

    def test_the_wait_is_switched_off_and_the_connection_closed_when_the_barrier_fails(self):
        """A timeout must not leave the wait on for the rest of the request."""
        statements, connection = self.run_barrier(fail_on="SELECT 1")
        self.assertEqual(statements[-1], "SET SESSION wsrep_sync_wait = 0")
        self.assertTrue(connection.closed)
