"""
Configuration for the orders app.
"""

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Configuration for the orders app."""

    name = "nau_openedx_extensions.orders"
    label = "nau_orders"
    verbose_name = "NAU Orders"
    # Required for edx-platform to install the app from the ``lms.djangoapp`` entry point.
    plugin_app = {}
