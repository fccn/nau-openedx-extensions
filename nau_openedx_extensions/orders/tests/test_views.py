"""
Tests for the order history page.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from common.djangoapps.student.tests.factories import UserFactory
from django.test import TestCase
from django.urls import reverse

from nau_openedx_extensions.orders.api import record_order

PLACED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def record(user, number, **overrides):
    """Record an order with sensible defaults."""
    kwargs = {
        "user": user,
        "number": number,
        "provider": "zeitlabs",
        "status": "paid",
        "currency": "EUR",
        "total": Decimal("25.00"),
        "placed_at": PLACED_AT,
        "items": [{"title": "Verified track", "course_id": "course-v1:NAU+ZEITPOC+2026_T3", "mode": "verified",
                   "unit_price": Decimal("25.00")}],
    }
    kwargs.update(overrides)
    return record_order(**kwargs)


class OrderHistoryViewTest(TestCase):
    """Tests for OrderHistoryView."""

    def setUp(self):
        self.user = UserFactory(password="test")
        self.url = reverse("nau-openedx-extensions:nau_order_history")
        self.client.login(username=self.user.username, password="test")

    def test_url(self):
        """The page lives under the plugin's URL namespace."""
        self.assertEqual(self.url, "/nau-openedx-extensions/orders/")

    def test_requires_login(self):
        """Anonymous users are sent to the login page."""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])

    def test_empty_state(self):
        """A learner without purchases sees the empty message."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You have not made any purchases yet.")
        self.assertNotContains(response, "<table")

    def test_lists_only_own_orders_newest_first(self):
        """The page lists the learner's orders, newest first, and never another learner's."""
        record(self.user, "NAU-100001", placed_at=PLACED_AT)
        record(self.user, "NAU-100002", placed_at=PLACED_AT + timedelta(days=1), status="pending",
               payment_method="REFMB")
        record(UserFactory(), "NAU-100003")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([order.number for order in response.context["orders"]], ["NAU-100002", "NAU-100001"])
        self.assertNotContains(response, "NAU-100003")

    def test_row_contents(self):
        """A row shows items, method, amount, status label and the document links that exist."""
        record(
            self.user, "NAU-100001", payment_method="VISA",
            invoice_url="https://lms.example.com/payment/v1/invoice/NAU-100001/",
            receipt_url="https://financial-manager.example.com/receipts/NAU-100001.pdf",
            items=[{"title": "Verified track", "course_id": "course-v1:NAU+ZEITPOC+2026_T3",
                    "unit_price": Decimal("12.50"), "quantity": 2}],
        )
        record(self.user, "NAU-100002", status="pending", payment_method="REFMB")

        response = self.client.get(self.url)

        self.assertContains(response, "Verified track")
        self.assertContains(response, "&times;2")
        self.assertContains(response, "course-v1:NAU+ZEITPOC+2026_T3")
        self.assertContains(response, "VISA")
        self.assertContains(response, "25.00 EUR")
        self.assertContains(response, 'href="https://lms.example.com/payment/v1/invoice/NAU-100001/"')
        self.assertContains(response, 'href="https://financial-manager.example.com/receipts/NAU-100001.pdf"')
        self.assertContains(response, "nau-orders-status-paid")
        self.assertContains(response, "nau-orders-status-pending")
        self.assertContains(response, "Awaiting payment")

    def test_pagination(self):
        """Twenty orders per page, with navigation links."""
        for index in range(21):
            record(self.user, f"NAU-{100001 + index}", placed_at=PLACED_AT + timedelta(minutes=index))

        first = self.client.get(self.url)
        second = self.client.get(self.url, {"page": 2})

        self.assertEqual(len(first.context["orders"]), 20)
        self.assertContains(first, "Page 1 of 2")
        self.assertContains(first, "?page=2")
        self.assertEqual([order.number for order in second.context["orders"]], ["NAU-100001"])
        self.assertContains(second, "?page=1")


class OrderHistoryIsolationTest(TestCase):
    """
    A learner can only ever see their own orders. Nothing in the request can widen that.
    """

    def setUp(self):
        self.learner = UserFactory(password="test")
        self.other = UserFactory(password="test")
        self.staff = UserFactory(password="test", is_staff=True, is_superuser=True)
        self.url = reverse("nau-openedx-extensions:nau_order_history")

        self.own = record(self.learner, "NAU-OWN-1", items=[{"title": "Own course", "unit_price": Decimal("1.00")}])
        self.others = [
            record(self.other, f"NAU-OTHER-{index}", placed_at=PLACED_AT + timedelta(days=index),
                   items=[{"title": f"Other course {index}", "unit_price": Decimal("1.00")}])
            for index in range(3)
        ]
        self.staff_order = record(
            self.staff, "NAU-STAFF-1", items=[{"title": "Staff course", "unit_price": Decimal("1.00")}],
        )

    def assert_only_own(self, response, user, numbers):
        """The page lists exactly the given numbers and no other order's number, title or item."""
        self.assertEqual(response.status_code, 200)
        self.assertEqual([order.number for order in response.context["orders"]], numbers)
        for order in list(self.others) + [self.own, self.staff_order]:
            if order.user != user:
                self.assertNotContains(response, order.number)
                for item in order.items.all():
                    self.assertNotContains(response, item.title)

    def test_learner_sees_only_own_orders(self):
        """With other learners' orders in the table, the page shows only the requesting learner's."""
        self.client.login(username=self.learner.username, password="test")
        response = self.client.get(self.url)
        self.assert_only_own(response, self.learner, ["NAU-OWN-1"])

    def test_learner_without_orders_sees_nothing_although_others_have_orders(self):
        """A learner with no purchases gets the empty state, not someone else's list."""
        newcomer = UserFactory(password="test")
        self.client.login(username=newcomer.username, password="test")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["orders"]), [])
        self.assertContains(response, "You have not made any purchases yet.")
        for order in list(self.others) + [self.own, self.staff_order]:
            self.assertNotContains(response, order.number)

    def test_staff_and_superusers_see_only_their_own_orders(self):
        """Staff and superuser status gives no access to other learners' orders on this page."""
        self.client.login(username=self.staff.username, password="test")
        response = self.client.get(self.url)
        self.assert_only_own(response, self.staff, ["NAU-STAFF-1"])

    def test_query_parameters_cannot_select_another_user(self):
        """No request parameter widens the queryset: user, username, number or id are all ignored."""
        self.client.login(username=self.learner.username, password="test")
        for params in (
            {"user": self.other.pk},
            {"user_id": self.other.pk},
            {"username": self.other.username},
            {"number": "NAU-OTHER-0"},
            {"order": self.others[0].pk},
            {"page": 1, "user": self.other.pk},
        ):
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assert_only_own(response, self.learner, ["NAU-OWN-1"])

    def test_pagination_counts_only_own_orders(self):
        """Other learners' orders never create extra pages or show up on a later page."""
        for index in range(25):
            record(self.other, f"NAU-OTHER-BULK-{index}", placed_at=PLACED_AT + timedelta(hours=index),
                   items=[{"title": f"Other bulk {index}", "unit_price": Decimal("1.00")}])
        self.client.login(username=self.learner.username, password="test")

        first = self.client.get(self.url)
        self.assertFalse(first.context["is_paginated"])
        self.assertEqual([order.number for order in first.context["orders"]], ["NAU-OWN-1"])
        self.assertNotContains(first, "NAU-OTHER-BULK")

        beyond = self.client.get(self.url, {"page": 2})
        self.assertEqual(beyond.status_code, 404)

    def test_switching_user_switches_the_list(self):
        """The list follows the session user, never a cached or previous result."""
        self.client.login(username=self.learner.username, password="test")
        self.assert_only_own(self.client.get(self.url), self.learner, ["NAU-OWN-1"])

        self.client.logout()
        self.client.login(username=self.other.username, password="test")
        self.assert_only_own(
            self.client.get(self.url), self.other, ["NAU-OTHER-2", "NAU-OTHER-1", "NAU-OTHER-0"],
        )
