import logging

from django.conf import settings

from . import logfile


def get_backend():
    """
    Use Message gateway backend defined in the settings.
    """
    backend_setting = getattr(settings, "NAU_MESSAGE_GATEWAY_BACKEND", "log_file")
    if backend_setting == "log_file":
        return logfile.Backend()
    else:
        raise ValueError(
            u"Invalid NAU_MESSAGE_GATEWAY_BACKEND setting value: %s" % backend_setting
        )
