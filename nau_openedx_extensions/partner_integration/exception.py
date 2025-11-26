"""Custom exceptions for the data extractor module."""


class CertificateNoDataProvidedException(Exception):
    """
    Custom exception for certificate access errors.

    Exception raised when no data provided to fetch certificates.
    """

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = (
                "No data provided to fetch certificates. Please provide at least one NIF "
                "or email, or ensure the client's query scope contains logic to access data."
            )


class CertificateInvalidDataProvidedException(Exception):
    """
    Custom exception for certificate access errors.

    Exception raised when the data provided for extraction is not valid.
    """

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = (
                "Invalid data provided for certificate access. "
                "Please verify the request parameters."
            )


class CertificateInternalErrorException(Exception):
    """
    Custom exception for internal errors during certificate access.

    Exception raised when the query fails or access issues occur.
    """

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = (
                "An internal error occurred while accessing certificates. Please verify the "
                "request parameters and try again later. Contact support if the issue persists."
            )


class CertificateInactiveClientException(Exception):
    """Custom exception for inactive API clients."""

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = "The API client is inactive. Please contact support to reactivate the client."


class PartnerCourseOwnerException(Exception):
    """Custom exception for internal errors during certificate access."""

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = "You are not allowed to get information about this course."
