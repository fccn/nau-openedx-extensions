"""
Tests for the circuit breaker.
"""
from django.test import SimpleTestCase

from nau_openedx_extensions.read_replica.breaker import CircuitBreaker


class CircuitBreakerTest(SimpleTestCase):
    """
    Open for a while, then closed again by itself.
    """

    def setUp(self):
        super().setUp()
        self.now = 1000.0
        self.breaker = CircuitBreaker(clock=lambda: self.now)

    def test_it_starts_closed(self):
        """A new breaker lets everything through."""
        self.assertFalse(self.breaker.is_open())

    def test_it_stays_open_for_the_given_time_and_then_closes(self):
        """The window is exact: open before it ends, closed from the end."""
        self.breaker.trip(10)
        self.assertTrue(self.breaker.is_open())
        self.now += 9.9
        self.assertTrue(self.breaker.is_open())
        self.now += 0.1
        self.assertFalse(self.breaker.is_open())

    def test_a_shorter_trip_never_closes_it_early(self):
        """Tripping again with a shorter window keeps the longer one."""
        self.breaker.trip(30)
        self.breaker.trip(5)
        self.now += 20
        self.assertTrue(self.breaker.is_open())

    def test_a_new_trip_extends_the_window(self):
        """Tripping again later opens it for a full new window."""
        self.breaker.trip(10)
        self.now += 8
        self.breaker.trip(10)
        self.now += 8
        self.assertTrue(self.breaker.is_open())

    def test_reset_closes_it(self):
        """reset() closes it at once."""
        self.breaker.trip(10)
        self.breaker.reset()
        self.assertFalse(self.breaker.is_open())
