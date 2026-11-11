"""
What the routing knows about the request being served by the current thread.
"""
import threading


class _RequestState(threading.local):
    """
    Per thread state, because the LMS serves one request per thread and every thread has its own database
    connections. ``active`` is true while a GET is being served from the read replica and ``wrote`` once the
    request has written, after which the rest of the request reads from the writer.
    """

    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        """
        Forget the previous request.
        """
        self.active = False
        self.wrote = False
        self.path = None


request_state = _RequestState()
