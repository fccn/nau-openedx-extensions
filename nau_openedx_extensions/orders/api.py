"""
Recording API of the orders app.

These two functions are the whole contract between a payment plugin and NAU. A plugin calls
``record_order`` when a purchase exists and ``update_order`` whenever it changes the purchase
afterwards. See docs/decisions/0002-orders-app.rst, section 4.

Both run in a transaction and only touch the database. They never call the payment plugin back.
"""

from django.db import transaction

from nau_openedx_extensions.orders.models import Order, OrderItem

ITEM_REQUIRED_FIELDS = ("title", "unit_price")
ITEM_OPTIONAL_FIELDS = ("course_id", "mode", "quantity")

_UNSET = object()


def _validate_status(status):
    """Raise ``ValueError`` when ``status`` is not one of ``Order.Status``."""
    if status not in Order.Status.values:
        raise ValueError(f"Unknown order status {status!r}; expected one of {', '.join(Order.Status.values)}")


def _validate_items(items):
    """Return ``items`` as a list of dicts, raising ``ValueError`` when one is malformed."""
    items = list(items)
    if not items:
        raise ValueError("An order needs at least one item")
    allowed = set(ITEM_REQUIRED_FIELDS) | set(ITEM_OPTIONAL_FIELDS)
    for index, item in enumerate(items):
        missing = [field for field in ITEM_REQUIRED_FIELDS if field not in item]
        if missing:
            raise ValueError(f"Item {index} is missing required field(s): {', '.join(missing)}")
        unknown = set(item) - allowed
        if unknown:
            raise ValueError(f"Item {index} has unknown field(s): {', '.join(sorted(unknown))}")
    return items


@transaction.atomic
def record_order(  # pylint: disable=too-many-arguments
    *,
    user,
    number,
    provider,
    status,
    currency,
    total,
    placed_at,
    items,
    payment_method="",
    invoice_url="",
    receipt_url="",
):
    """
    Record a purchase, or update it when ``number`` already exists.

    The call is idempotent on ``number``: a second call for the same number updates every field
    given here and replaces the items. The ``user`` of an existing order is never changed.

    :param user: The learner who made the purchase.
    :param number: The number the learner sees; the payment plugin's invoice or order number.
    :param provider: Slug of the payment plugin recording the order.
    :param status: One of ``Order.Status`` values.
    :param currency: ISO 4217 code.
    :param total: Amount charged, tax included.
    :param placed_at: When the learner committed to the purchase.
    :param items: Iterable of dicts with ``title`` and ``unit_price``, and optionally ``course_id``,
        ``mode`` and ``quantity``.
    :param payment_method: Label of the payment method, when known.
    :param invoice_url: Absolute URL of the invoice page, when it exists.
    :param receipt_url: Absolute URL of the receipt, when it exists.
    :return: The ``Order``.
    :raises ValueError: On an unknown status or a malformed item.
    """
    _validate_status(status)
    items = _validate_items(items)

    order, created = Order.objects.select_for_update().get_or_create(
        number=number,
        defaults={
            "user": user,
            "provider": provider,
            "status": status,
            "currency": currency,
            "total": total,
            "placed_at": placed_at,
            "payment_method": payment_method,
            "invoice_url": invoice_url,
            "receipt_url": receipt_url,
        },
    )
    if not created:
        order.provider = provider
        order.status = status
        order.currency = currency
        order.total = total
        order.placed_at = placed_at
        order.payment_method = payment_method
        order.invoice_url = invoice_url
        order.receipt_url = receipt_url
        order.save()
        order.items.all().delete()

    OrderItem.objects.bulk_create([OrderItem(order=order, **item) for item in items])
    return order


@transaction.atomic
def update_order(  # pylint: disable=too-many-arguments
    *,
    number,
    status=_UNSET,
    payment_method=_UNSET,
    paid_at=_UNSET,
    invoice_url=_UNSET,
    receipt_url=_UNSET,
):
    """
    Change one or more fields of an existing order. Arguments not passed are left untouched.

    :param number: The order number.
    :param status: One of ``Order.Status`` values.
    :param payment_method: Label of the payment method.
    :param paid_at: When the payment was confirmed; ``None`` clears it.
    :param invoice_url: Absolute URL of the invoice page.
    :param receipt_url: Absolute URL of the receipt.
    :return: The updated ``Order``.
    :raises Order.DoesNotExist: When no order has that number.
    :raises ValueError: On an unknown status, or when nothing is passed to update.
    """
    changes = {
        name: value
        for name, value in (
            ("status", status),
            ("payment_method", payment_method),
            ("paid_at", paid_at),
            ("invoice_url", invoice_url),
            ("receipt_url", receipt_url),
        )
        if value is not _UNSET
    }
    if not changes:
        raise ValueError("update_order needs at least one field to update")
    if "status" in changes:
        _validate_status(changes["status"])

    order = Order.objects.select_for_update().get(number=number)
    for name, value in changes.items():
        setattr(order, name, value)
    order.save(update_fields=[*changes, "updated_at"])
    return order
