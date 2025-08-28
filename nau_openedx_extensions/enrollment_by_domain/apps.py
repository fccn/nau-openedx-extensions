"""
Configuration for the enrollment by domain app.
"""

from django.apps import AppConfig


class EnrollmentByDomainConfig(AppConfig):
    """Configuration for the enrollment by domain app."""

    name = "nau_openedx_extensions.enrollment_by_domain"
    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
                "test": {"relative_path": "settings.test"},
                "production": {"relative_path": "settings.production"},
            },
        },
    }
