"""URL patterns of the orders app."""

from django.urls import path

from nau_openedx_extensions.orders import views

urlpatterns = [
    path("", views.OrderHistoryView.as_view(), name="nau_order_history"),
]
