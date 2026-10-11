"""
Views of the orders app.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from nau_openedx_extensions.orders.models import Order


class OrderHistoryView(LoginRequiredMixin, ListView):
    """
    The logged-in learner's purchases, newest first.

    Reads only the orders app tables. A learner can only ever see their own orders: the queryset
    is filtered on ``request.user`` and the view takes no lookup parameter.
    """

    template_name = "nau_orders/order_history.html"
    context_object_name = "orders"
    paginate_by = 20

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items")
