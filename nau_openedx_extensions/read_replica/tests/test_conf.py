"""
Tests for the settings accessors.
"""
from django.test import SimpleTestCase
from django.test.utils import override_settings

from nau_openedx_extensions.read_replica import conf


class AllowListTest(SimpleTestCase):
    """
    The GET allow-list.
    """

    def test_defaults_route_nothing(self):
        """Without configuration, no path is allowed and nothing is installed."""
        self.assertFalse(conf.routing_enabled())
        self.assertFalse(conf.debug_header_enabled())
        self.assertFalse(conf.get_is_allowed("/api/courseware/course/x"))

    @override_settings(NAU_READ_REPLICA_GET_ALLOWLIST=[r"^/api/course_home/outline/", r"^/api/learner_home/init$"])
    def test_patterns_are_matched_from_the_start_of_the_path(self):
        """A pattern matches the beginning of the path, not any place in it."""
        self.assertTrue(conf.get_is_allowed("/api/course_home/outline/course-v1:A+B+C"))
        self.assertTrue(conf.get_is_allowed("/api/learner_home/init"))
        self.assertFalse(conf.get_is_allowed("/api/learner_home/init/extra"))
        self.assertFalse(conf.get_is_allowed("/other/api/course_home/outline/x"))

    @override_settings(NAU_READ_REPLICA_GET_ALLOWLIST=["([unclosed", r"^/ok/"])
    def test_an_invalid_pattern_is_ignored_and_logged(self):
        """A bad pattern must never break requests: the valid ones still work."""
        with self.assertLogs("nau_openedx_extensions.read_replica.conf", level="ERROR") as logs:
            self.assertTrue(conf.get_is_allowed("/ok/x"))
        self.assertIn("([unclosed", logs.output[0])
        self.assertFalse(conf.get_is_allowed("/nope"))

    @override_settings(
        NAU_READ_REPLICA_ROUTING_ENABLED=True,
        NAU_READ_REPLICA_DEBUG_HEADER=True,
    )
    def test_flags_are_read_from_the_settings(self):
        """The flags follow the settings."""
        self.assertTrue(conf.routing_enabled())
        self.assertTrue(conf.debug_header_enabled())


class BreakerSettingsTest(SimpleTestCase):
    """
    The numbers of the circuit breaker.
    """

    def test_defaults(self):
        """The barrier is slow above 250 ms and the replica is skipped for ten seconds."""
        self.assertEqual(conf.barrier_slow_ms(), 250)
        self.assertEqual(conf.breaker_seconds(), 10)

    @override_settings(NAU_READ_REPLICA_BARRIER_SLOW_MS="100", NAU_READ_REPLICA_BREAKER_SECONDS=3)
    def test_they_come_from_the_settings(self):
        """Both are settings, a string from the environment is accepted."""
        self.assertEqual(conf.barrier_slow_ms(), 100)
        self.assertEqual(conf.breaker_seconds(), 3)
