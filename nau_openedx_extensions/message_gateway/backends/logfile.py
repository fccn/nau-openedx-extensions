"""
Log backend for the message gateway integration
"""
from __future__ import absolute_import, unicode_literals

import logging

from .base import BaseBackend

log = logging.getLogger("nau_message_gateway")


class Backend(BaseBackend):
    """
    Backend that just logs the message that would be sent using the message gateway integration.
    """
    def send_message(self, message, recipients):
        log.info(
            "Sending message with id (%s) to %d recipients", message.id, len(recipients)
        )
