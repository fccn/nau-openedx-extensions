"""
Configuration for the course certificate app.
"""

from django.apps import AppConfig


class CoursecertificateConfig(AppConfig):
    """Configuration for the course certificate app."""

    name = "nau_openedx_extensions.coursecertificate"
    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
                "test": {"relative_path": "settings.test"},
                "production": {"relative_path": "settings.production"},
            },
        },
    }

    def ready(self):
        """
        Import handlers to ensure they are registered.
        """
        # pylint: disable=import-outside-toplevel,unused-import
        import nau_openedx_extensions.coursecertificate.handlers
