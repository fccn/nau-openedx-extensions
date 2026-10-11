"""
Tests for the orders app models.
"""

from datetime import datetime, timezone
from decimal import Decimal

from common.djangoapps.student.tests.factories import UserFactory
from django.db import IntegrityError
from django.test import TestCase

from nau_openedx_extensions.orders.models import Order, OrderItem


class OrderModelTest(TestCase):
    """Tests for Order and OrderItem."""

    def setUp(self):
        self.user = UserFactory()
        self.order = Order.objects.create(
            user=self.user,
            number="NAU-100001",
            provider="zeitlabs",
            status=Order.Status.PENDING,
            currency="EUR",
            total=Decimal("25.00"),
            placed_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        )

    def test_str(self):
        """The string shows the number and the status label."""
        self.assertEqual(str(self.order), "NAU-100001 (Awaiting payment)")

    def test_item_str(self):
        """The item string shows the order number, the title and the quantity."""
        item = OrderItem.objects.create(order=self.order, title="Verified track", unit_price=Decimal("25.00"))
        self.assertEqual(str(item), "NAU-100001: Verified track x1")

    def test_number_is_unique(self):
        """Two orders cannot share a number."""
        with self.assertRaises(IntegrityError):
            Order.objects.create(
                user=self.user,
                number="NAU-100001",
                provider="zeitlabs",
                status=Order.Status.PAID,
                currency="EUR",
                total=Decimal("1.00"),
                placed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
            )

    def test_default_ordering_is_newest_first(self):
        """Orders list newest placed first."""
        newer = Order.objects.create(
            user=self.user,
            number="NAU-100002",
            provider="zeitlabs",
            status=Order.Status.PAID,
            currency="EUR",
            total=Decimal("1.00"),
            placed_at=datetime(2026, 10, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(list(Order.objects.all()), [newer, self.order])

    def test_items_follow_order_deletion(self):
        """Deleting an order removes its items."""
        OrderItem.objects.create(order=self.order, title="Verified track", unit_price=Decimal("25.00"))
        self.order.delete()
        self.assertFalse(OrderItem.objects.exists())

    def test_orders_follow_user_deletion(self):
        """Deleting the user removes their orders, following account retirement."""
        self.user.delete()
        self.assertFalse(Order.objects.exists())

    def test_status_vocabulary(self):
        """The four statuses of the design note, and only those."""
        self.assertEqual(list(Order.Status.values), ["pending", "paid", "cancelled", "refunded"])
