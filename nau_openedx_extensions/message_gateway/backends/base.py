class BaseBackend(object):
    """
    Base class for NAU Message Gateway backend.
    """

    def send_message(self, message, recipients):
        """
        Send given message to the recipients.
        """
        raise NotImplementedError
