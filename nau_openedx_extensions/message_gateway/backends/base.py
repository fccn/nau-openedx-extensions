"""
Base backend for the message gateway integration.
"""


from __future__ import unicode_literals


class BaseBackend:
    """
    Base class for NAU Message Gateway backend.
    """

    def send_message(self, message, recipients):
        """
        Send given message to the recipients.
        """
        raise NotImplementedError
