"""
Cross-package integration: the PayGate processor for zeitlabs-payments reporting to the orders app.

Runs the real PayGate callback views against the real zeitlabs-payments cart and invoice tables in the
LMS test database, with only PayGate's HTTP API stubbed, and asserts the rows the orders app ends up
with. Skipped when the payment packages are not installed in the test environment.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
import responses
from common.djangoapps.course_modes.tests.factories import CourseModeFactory
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.tests.factories import UserFactory
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory

from nau_openedx_extensions.orders.models import Order

zeitlabs_models = pytest.importorskip("zeitlabs_payments.models", exc_type=ImportError)
zeitlabs_paygate_orders = pytest.importorskip("zeitlabs_paygate.orders", exc_type=ImportError)

Cart = zeitlabs_models.Cart
CartItem = zeitlabs_models.CartItem
CatalogueItem = zeitlabs_models.CatalogueItem
Invoice = zeitlabs_models.Invoice
sync_cart_order = zeitlabs_paygate_orders.sync_cart_order

PAYGATE_SEARCH_URL = "https://paygate.test/BackOfficeSearchTransactions"

PAYMENT_SETTINGS = {
    "IS_ZEITLABS_PAYMENTS_ENABLED": True,
    "ZEITLABS_PAYMENTS_SETTINGS": {"invoice_prefix": "TST", "valid_currency": "EUR"},
    "PAYGATE_SETTINGS": {
        "access_token": "token",
        "merchant_code": "MERCHANT",
        "api_basic_auth_user": "user",
        "api_basic_auth_pass": "pass",
        "api_checkout_url": "https://paygate.test/CheckOut",
        "api_back_search_transactions": PAYGATE_SEARCH_URL,
        "callback_server_allowed_networks": ["10.0.0.0/8"],
    },
}


@override_settings(**PAYMENT_SETTINGS)
class PayGateOrdersIntegrationTest(TestCase):
    """A purchase through the PayGate processor ends up in the orders app, step by step."""

    def setUp(self):
        self.site = Site.objects.get_current()
        self.learner = UserFactory(password="test")
        self.course = CourseOverviewFactory(
            id=CourseKey.from_string("course-v1:NAU+ORDERS+2026"), display_name="Orders course",
        )
        CourseModeFactory(course_id=self.course.id, mode_slug="verified", sku="ORDERS-SKU", min_price=25)
        self.catalogue_item = CatalogueItem.objects.create(
            sku="ORDERS-SKU", type=CatalogueItem.ItemType.PAID_COURSE, title="Orders course - verified",
            item_ref_id=str(self.course.id), price=Decimal("25.00"), currency="EUR",
        )
        self.cart = Cart.objects.create(user=self.learner, status=Cart.Status.PROCESSING)
        CartItem.objects.create(
            cart=self.cart, catalogue_item=self.catalogue_item,
            original_price=Decimal("25.00"), final_price=Decimal("25.00"),
        )
        self.payment_ref = f"{self.site.id}-{self.cart.id}"
        self.client.login(username=self.learner.username, password="test")

    def completed_transaction(self, method="REFMB"):
        """What PayGate's search API returns for a paid reference."""
        return [{
            "MERCHANT_CODE": "MERCHANT", "STATUS_CODE": "C", "PAYMENT_REF": self.payment_ref,
            "TRANSACTION_ID": "T-1", "PAYMENT_TYPE_CODE": method, "PAYMENT_AMOUNT": "25.00",
        }]

    def test_sync_maps_a_real_cart_onto_the_orders_contract(self):
        """The mapping resolves the course mode from the real CourseMode table and writes a real row."""
        sync_cart_order(self.cart, self.site.id, "pending")

        order = Order.objects.get(number=self.payment_ref)
        self.assertEqual(order.user, self.learner)
        self.assertEqual(order.provider, "zeitlabs")
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.currency, "EUR")
        self.assertEqual(order.total, Decimal("25.00"))
        self.assertEqual(order.placed_at, self.cart.created_at)
        item = order.items.get()
        self.assertEqual(item.title, "Orders course - verified")
        self.assertEqual(item.course_id, "course-v1:NAU+ORDERS+2026")
        self.assertEqual(item.mode, "verified")
        self.assertEqual(item.unit_price, Decimal("25.00"))

    @responses.activate
    def test_multibanco_purchase_pending_then_paid_then_on_the_page(self):
        """
        Learner returns from PayGate before paying the reference: order is pending.
        PayGate's server callback confirms it later: order is paid, with invoice link and date,
        the learner is enrolled, and the page shows the paid row.
        """
        responses.post(PAYGATE_SEARCH_URL, json=[])
        response = self.client.get(reverse("zeitlabs_paygate:callback_success"), {"payment_ref": self.payment_ref})
        self.assertEqual(response.status_code, 200)
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.status, Cart.Status.PAYMENT_PENDING)

        order = Order.objects.get(number=self.payment_ref)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment_method, "")
        self.assertEqual(order.invoice_url, "")
        self.assertIsNone(order.paid_at)

        responses.replace(responses.POST, PAYGATE_SEARCH_URL, json=self.completed_transaction())
        response = self.client.post(
            reverse("zeitlabs_paygate:callback_server"),
            data=f'{{"payment_ref": "{self.payment_ref}", "statusCode": "C"}}',
            content_type="application/json", REMOTE_ADDR="10.1.2.3",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.status, Cart.Status.PAID)
        invoice = Invoice.objects.get(cart=self.cart)
        self.assertTrue(CourseEnrollment.is_enrolled(self.learner, self.course.id))

        order.refresh_from_db()
        self.assertEqual(Order.objects.count(), 1, "the same order is updated, not duplicated")
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.payment_method, "REFMB")
        self.assertEqual(order.paid_at, invoice.paid_at)
        self.assertEqual(
            order.invoice_url, f"https://lms.example.com/payment/v1/invoice/{invoice.invoice_number}/",
        )
        self.assertEqual(order.items.get().title, "Orders course - verified")

        page = self.client.get(reverse("nau-openedx-extensions:nau_order_history"))
        self.assertContains(page, self.payment_ref)
        self.assertContains(page, "nau-orders-status-paid")
        self.assertContains(page, f'href="https://lms.example.com/payment/v1/invoice/{invoice.invoice_number}/"')

    @responses.activate
    def test_card_purchase_paid_on_return(self):
        """A card payment confirmed on the success return is recorded as paid in one step."""
        responses.post(PAYGATE_SEARCH_URL, json=self.completed_transaction(method="VISA"))
        response = self.client.get(reverse("zeitlabs_paygate:callback_success"), {"payment_ref": self.payment_ref})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/payment/v1/invoice/", response["Location"])

        order = Order.objects.get(number=self.payment_ref)
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.payment_method, "VISA")
        self.assertIsNotNone(order.paid_at)

    def test_cancelled_on_paygate(self):
        """Cancelling on the PayGate page records a cancelled order."""
        self.client.get(reverse("zeitlabs_paygate:callback_cancel"), {"payment_ref": self.payment_ref})
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.status, Cart.Status.CANCELLED)
        self.assertEqual(Order.objects.get(number=self.payment_ref).status, Order.Status.CANCELLED)

    def test_failed_on_paygate(self):
        """A failure reported by PayGate records a cancelled order."""
        self.client.get(reverse("zeitlabs_paygate:callback_failure"), {"payment_ref": self.payment_ref})
        self.assertEqual(Order.objects.get(number=self.payment_ref).status, Order.Status.CANCELLED)

    @responses.activate
    def test_orders_app_failure_does_not_break_the_payment(self):
        """If recording fails, the payment is still confirmed and fulfilled; the failure is logged."""
        responses.post(PAYGATE_SEARCH_URL, json=self.completed_transaction())
        with patch("nau_openedx_extensions.orders.api.record_order", side_effect=RuntimeError("orders down")):
            with self.assertLogs("zeitlabs_paygate.orders", level="ERROR") as logs:
                response = self.client.post(
                    reverse("zeitlabs_paygate:callback_server"),
                    data=f'{{"payment_ref": "{self.payment_ref}"}}',
                    content_type="application/json", REMOTE_ADDR="10.1.2.3",
                )
        self.assertEqual(response.status_code, 200)
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.status, Cart.Status.PAID)
        self.assertTrue(Invoice.objects.filter(cart=self.cart).exists())
        self.assertFalse(Order.objects.exists())
        self.assertIn("Failed to report cart", logs.output[0])

    def test_other_learner_does_not_see_the_order(self):
        """The order recorded for one learner is invisible to another."""
        sync_cart_order(self.cart, self.site.id, "pending")
        other = UserFactory(password="test")
        self.client.logout()
        self.client.login(username=other.username, password="test")
        page = self.client.get(reverse("nau-openedx-extensions:nau_order_history"))
        self.assertNotContains(page, self.payment_ref)
        self.assertContains(page, "You have not made any purchases yet.")
