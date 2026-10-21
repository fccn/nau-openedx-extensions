"""
A circuit breaker for the read replica.

The causal barrier waits until the replica has applied what the cluster committed, so its latency is the replication
lag of the moment. Measured on a three node lab with two applier threads: 1 to 6 ms when the replica only serves reads,
and about 0.9 s (up to 2.6 s) while the writer is busy enough for Galera flow control to throttle the replica. When
the replica lags, every routed request would wait for it, up to ``repl.causal_read_timeout``, and pin a worker for
the whole time.

The breaker stops that. It opens, for a few seconds, when the barrier fails or is slow, and while it is open the
requests skip the replica and are served by the writer at no extra cost. It is per process on purpose: no shared
state means no new dependency, and each process pays the slow barrier at most once per window.
"""
import threading
import time


class CircuitBreaker:
    """
    Open until a point in time, closed otherwise.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._open_until = 0.0
        self._lock = threading.Lock()

    def is_open(self):
        """
        Return whether the replica must be skipped right now.
        """
        return self._clock() < self._open_until

    def trip(self, seconds):
        """
        Open the breaker for ``seconds``, or keep it open for as long as it already was.
        """
        with self._lock:
            self._open_until = max(self._open_until, self._clock() + seconds)

    def reset(self):
        """
        Close the breaker.
        """
        with self._lock:
            self._open_until = 0.0


replica_breaker = CircuitBreaker()
