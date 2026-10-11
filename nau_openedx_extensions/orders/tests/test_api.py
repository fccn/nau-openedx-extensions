"""
Tests for the orders recording API.
"""

from datetime import datetime, timezone
from decimal import Decimal

from common.djangoapps.student.tests.factories import UserFactory
from django.test import TestCase

from nau_openedx_extensions.orders.api import record_order, update_order
from nau_openedx_extensions.orders.models import Order, OrderItem

PLACED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
PAID_AT = datetime(2026, 10, 1, 12, 5, tzinfo=timezone.utc)
ITEM = {"title": "Verified track", "course_id": "course-v1:NAU+ZEITPOC+2026_T3", "mode": "verified",
        "unit_price": Decimal("25.00")}


def record(user, **overrides):
    """Record an order with sensible defaults."""
    kwargs = {
        "user": user,
        "number": "NAU-100001",
        "provider": "zeitlabs",
        "status": "pending",
        "currency": "EUR",
        "total": Decimal("25.00"),
        "placed_at": PLACED_AT,
        "items": [ITEM],
    }
    kwargs.update(overrides)
    return record_order(**kwargs)


class RecordOrderTest(TestCase):
    """Tests for record_order."""

    def setUp(self):
        self.user = UserFactory()

    def test_creates_order_with_items(self):
        """A first call creates the order and its items with the given values."""
        order = record(self.user, payment_method="REFMB")

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.number, "NAU-100001")
        self.assertEqual(order.provider, "zeitlabs")
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment_method, "REFMB")
        self.assertEqual(order.currency, "EUR")
        self.assertEqual(order.total, Decimal("25.00"))
        self.assertEqual(order.placed_at, PLACED_AT)
        self.assertIsNone(order.paid_at)
        self.assertEqual(order.invoice_url, "")
        self.assertEqual(order.receipt_url, "")

        item = order.items.get()
        self.assertEqual(item.title, "Verified track")
        self.assertEqual(item.course_id, "course-v1:NAU+ZEITPOC+2026_T3")
        self.assertEqual(item.mode, "verified")
        self.assertEqual(item.quantity, 1)
        self.assertEqual(item.unit_price, Decimal("25.00"))

    def test_items_only_need_title_and_unit_price(self):
        """Optional item fields take their defaults."""
        order = record(self.user, items=[{"title": "Bundle", "unit_price": Decimal("10.00")}])
        item = order.items.get()
        self.assertEqual((item.course_id, item.mode, item.quantity), ("", "", 1))

    def test_is_idempotent_on_number(self):
        """A second call for the same number updates the fields and replaces the items."""
        first = record(self.user)
        other_user = UserFactory()

        second = record(
            other_user,
            status="paid",
            total=Decimal("30.00"),
            payment_method="VISA",
            invoice_url="https://lms.example.com/invoice/NAU-100001/",
            items=[{"title": "Verified track", "unit_price": Decimal("20.00")},
                   {"title": "Extra", "unit_price": Decimal("10.00"), "quantity": 2}],
        )

        self.assertEqual(second.pk, first.pk)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(second.user, self.user, "the owner of an existing order never changes")
        self.assertEqual(second.status, Order.Status.PAID)
        self.assertEqual(second.total, Decimal("30.00"))
        self.assertEqual(second.payment_method, "VISA")
        self.assertEqual(second.invoice_url, "https://lms.example.com/invoice/NAU-100001/")
        self.assertEqual(
            list(second.items.values_list("title", "quantity", "unit_price")),
            [("Verified track", 1, Decimal("20.00")), ("Extra", 2, Decimal("10.00"))],
        )
        self.assertEqual(OrderItem.objects.count(), 2)

    def test_rejects_unknown_status(self):
        """Only the four statuses are accepted, and nothing is written otherwise."""
        with self.assertRaisesRegex(ValueError, "Unknown order status 'open'"):
            record(self.user, status="open")
        self.assertFalse(Order.objects.exists())

    def test_rejects_empty_items(self):
        """An order needs at least one item."""
        with self.assertRaisesRegex(ValueError, "at least one item"):
            record(self.user, items=[])
        self.assertFalse(Order.objects.exists())

    def test_rejects_item_missing_required_field(self):
        """Every item needs a title and a unit price."""
        with self.assertRaisesRegex(ValueError, "Item 0 is missing required field\\(s\\): unit_price"):
            record(self.user, items=[{"title": "Verified track"}])
        self.assertFalse(Order.objects.exists())

    def test_rejects_item_with_unknown_field(self):
        """Unknown item fields are an error, not silently dropped."""
        with self.assertRaisesRegex(ValueError, "Item 0 has unknown field\\(s\\): sku"):
            record(self.user, items=[{**ITEM, "sku": "ZEITPOC1"}])
        self.assertFalse(Order.objects.exists())

    def test_accepts_any_iterable_of_items(self):
        """Items may be given as a generator."""
        order = record(self.user, items=(dict(ITEM) for _ in range(2)))
        self.assertEqual(order.items.count(), 2)


class UpdateOrderTest(TestCase):
    """Tests for update_order."""

    def setUp(self):
        self.user = UserFactory()
        self.order = record(self.user, payment_method="REFMB")

    def test_updates_only_given_fields(self):
        """Fields not passed keep their values."""
        updated = update_order(number="NAU-100001", status="paid", paid_at=PAID_AT)

        self.assertEqual(updated.pk, self.order.pk)
        self.assertEqual(updated.status, Order.Status.PAID)
        self.assertEqual(updated.paid_at, PAID_AT)
        self.assertEqual(updated.payment_method, "REFMB")
        self.assertEqual(updated.invoice_url, "")
        self.assertEqual(updated.items.count(), 1)

    def test_updates_urls_and_payment_method(self):
        """Invoice, receipt and payment method can be set after the fact."""
        update_order(
            number="NAU-100001",
            payment_method="MBWAY",
            invoice_url="https://lms.example.com/invoice/NAU-100001/",
            receipt_url="https://financial-manager.example.com/receipts/NAU-100001.pdf",
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_method, "MBWAY")
        self.assertEqual(self.order.invoice_url, "https://lms.example.com/invoice/NAU-100001/")
        self.assertEqual(self.order.receipt_url, "https://financial-manager.example.com/receipts/NAU-100001.pdf")
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_can_clear_paid_at(self):
        """Passing None clears the paid date."""
        update_order(number="NAU-100001", status="paid", paid_at=PAID_AT)
        update_order(number="NAU-100001", status="refunded", paid_at=None)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.REFUNDED)
        self.assertIsNone(self.order.paid_at)

    def test_rejects_unknown_status(self):
        """Only the four statuses are accepted, and nothing is written otherwise."""
        with self.assertRaisesRegex(ValueError, "Unknown order status 'complete'"):
            update_order(number="NAU-100001", status="complete", paid_at=PAID_AT)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertIsNone(self.order.paid_at)

    def test_rejects_call_without_changes(self):
        """A call that changes nothing is a programming error."""
        with self.assertRaisesRegex(ValueError, "at least one field"):
            update_order(number="NAU-100001")

    def test_unknown_number_raises(self):
        """There is nothing to update for an unknown number."""
        with self.assertRaises(Order.DoesNotExist):
            update_order(number="NAU-999999", status="paid")

    def test_touches_updated_at(self):
        """updated_at moves on every update."""
        before = self.order.updated_at
        update_order(number="NAU-100001", status="cancelled")
        self.order.refresh_from_db()
        self.assertGreater(self.order.updated_at, before)
