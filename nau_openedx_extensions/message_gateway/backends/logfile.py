import logging
from .base import BaseBackend

log = logging.getLogger("nau_message_gateway")

class Backend(BaseBackend):

    def send_message(self, message, recipients):
        log.info("Sending message with id (%s) to %d recipients", message.id, len(recipients))
