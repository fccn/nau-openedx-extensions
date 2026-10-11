"""
Models for the orders app.

The orders app is a ledger of what a payment plugin reported about a learner's purchases.
It holds no payment logic: the ``status`` field is a plain value set through
``nau_openedx_extensions.orders.api`` and never changed by this app on its own.
See docs/decisions/0002-orders-app.rst.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Order(models.Model):
    """
    One purchase of a learner, as reported by the payment plugin that processed it.
    """

    class Status(models.TextChoices):
        """The only statuses a payment plugin can report."""

        PENDING = "pending", _("Awaiting payment")
        PAID = "paid", _("Paid")
        CANCELLED = "cancelled", _("Cancelled")
        REFUNDED = "refunded", _("Refunded")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nau_orders",
        verbose_name=_("User"),
    )
    number = models.CharField(
        max_length=150,
        unique=True,
        help_text=_("The number the learner sees and quotes to support, set by the payment plugin."),
        verbose_name=_("Number"),
    )
    provider = models.CharField(
        max_length=50,
        help_text=_("Slug of the payment plugin that recorded the order."),
        verbose_name=_("Provider"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        verbose_name=_("Status"),
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Payment method label reported by the payment plugin, e.g. REFMB, MBWAY, VISA."),
        verbose_name=_("Payment method"),
    )
    currency = models.CharField(
        max_length=3,
        help_text=_("ISO 4217 code."),
        verbose_name=_("Currency"),
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Amount charged, tax included."),
        verbose_name=_("Total"),
    )
    placed_at = models.DateTimeField(
        help_text=_("When the learner committed to the purchase."),
        verbose_name=_("Placed at"),
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Paid at"),
    )
    invoice_url = models.URLField(
        max_length=500,
        blank=True,
        help_text=_("Absolute URL of the payment plugin's invoice page, if any."),
        verbose_name=_("Invoice URL"),
    )
    receipt_url = models.URLField(
        max_length=500,
        blank=True,
        help_text=_("Absolute URL of the official receipt, if any."),
        verbose_name=_("Receipt URL"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ["-placed_at", "-id"]

    def __str__(self):
        return f"{self.number} ({self.get_status_display()})"


class OrderItem(models.Model):
    """
    One line of an order: what the learner bought.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Order"),
    )
    title = models.CharField(
        max_length=255,
        help_text=_("What the learner bought, as shown at checkout."),
        verbose_name=_("Title"),
    )
    course_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Course key, when the item is a course mode."),
        verbose_name=_("Course ID"),
    )
    mode = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Course mode slug, when applicable."),
        verbose_name=_("Mode"),
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name=_("Quantity"),
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Tax included."),
        verbose_name=_("Unit price"),
    )

    class Meta:
        verbose_name = _("Order item")
        verbose_name_plural = _("Order items")
        ordering = ["id"]

    def __str__(self):
        return f"{self.order.number}: {self.title} x{self.quantity}"
