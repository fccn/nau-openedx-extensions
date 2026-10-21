"""
Tests for the router.
"""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from edx_django_utils.db.read_replica import READ_REPLICA_NAME, WRITER_NAME, ReadReplicaRouter

from nau_openedx_extensions.read_replica.context import replica_reads
from nau_openedx_extensions.read_replica.router import NauReadReplicaRouter
from nau_openedx_extensions.read_replica.state import request_state
from nau_openedx_extensions.read_replica.tests.helpers import replica_configured


class NauReadReplicaRouterTest(SimpleTestCase):
    """
    The router behaves like the upstream one, plus the way back to the writer.
    """

    def setUp(self):
        super().setUp()
        self.router = NauReadReplicaRouter()
        self.user_model = get_user_model()
        request_state.reset()
        self.addCleanup(request_state.reset)

    def test_it_is_the_upstream_router_with_extras(self):
        """The upstream names the routing relies on are still there after an upgrade."""
        self.assertTrue(issubclass(NauReadReplicaRouter, ReadReplicaRouter))
        self.assertEqual((READ_REPLICA_NAME, WRITER_NAME), ("read_replica", "default"))

    def test_reads_use_the_writer_by_default(self):
        """Outside a read_queries_only() block nothing changes."""
        with replica_configured():
            self.assertEqual(self.router.db_for_read(self.user_model), WRITER_NAME)

    def test_reads_use_the_replica_inside_the_block(self):
        """Inside the block reads go to the replica, like upstream."""
        with replica_configured(), replica_reads():
            self.assertEqual(self.router.db_for_read(self.user_model), READ_REPLICA_NAME)

    def test_reads_go_back_to_the_writer_after_a_write(self):
        """Once the request wrote, the rest of the request reads from the writer, even inside the block."""
        with replica_configured(), replica_reads():
            request_state.wrote = True
            self.assertEqual(self.router.db_for_read(self.user_model), WRITER_NAME)

    def test_writes_always_use_the_writer(self):
        """Writes never go to the replica."""
        with replica_configured(), replica_reads():
            self.assertEqual(self.router.db_for_write(self.user_model), WRITER_NAME)

    def test_saving_an_instance_from_the_replica_is_logged_in_a_routed_request(self):
        """A read-modify-write on a row loaded from the replica is reported with the path and the model."""
        stale = SimpleNamespace(_state=SimpleNamespace(db=READ_REPLICA_NAME))
        request_state.active, request_state.path = True, "/api/some/endpoint"
        with self.assertLogs("nau_openedx_extensions.read_replica.router", level="WARNING") as logs:
            self.assertEqual(self.router.db_for_write(self.user_model, instance=stale), WRITER_NAME)
        self.assertIn(self.user_model._meta.label, logs.output[0])  # pylint: disable=protected-access
        self.assertIn("/api/some/endpoint", logs.output[0])

    def test_saving_an_instance_from_the_writer_is_not_logged(self):
        """Instances of the writer, and saves outside a routed request, are silent."""
        from_writer = SimpleNamespace(_state=SimpleNamespace(db=WRITER_NAME))
        from_replica = SimpleNamespace(_state=SimpleNamespace(db=READ_REPLICA_NAME))
        request_state.active = True
        with self.assertNoLogs("nau_openedx_extensions.read_replica.router", level="WARNING"):
            self.router.db_for_write(self.user_model, instance=from_writer)
            self.router.db_for_write(self.user_model)
            request_state.active = False
            self.router.db_for_write(self.user_model, instance=from_replica)
