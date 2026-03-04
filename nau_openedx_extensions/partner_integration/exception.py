"""Custom exceptions for the data extractor module."""


class PartnerIntegrationNoDataProvidedException(Exception):
    """
    Custom exception for data access errors.

    Exception raised when no parameter provided to extract data.
    """

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = (
                "No parameter provided to extract data. Please provide at least one NIF "
                "or email, or ensure the client's query scope contains logic to access data."
            )


class PartnerIntegrationInvalidDataProvidedException(Exception):
    """
    Custom exception for data access errors.

    Exception raised when the data provided for extraction is not valid.
    """

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = (
                "Invalid data provided for data access. "
                "Please verify the request parameters."
            )


class PartnerIntegrationDataConflictException(Exception):
    """
    Custom exception for data access errors.

    Exception raised when the data provided for extraction causes a conflict.
    e.g., attempting to enroll a user who is already enrolled.
    """
    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = (
                "The data provided caused a conflict"
                "it means that the operation could not be completed due to existing data. "
                "Please verify the request parameters."
            )


class PartnerIntegrationInternalErrorException(Exception):
    """
    Custom exception for internal errors during data access.

    Exception raised when the query fails or access issues occur.
    """

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = (
                "An internal error occurred while accessing data. Please verify the "
                "request parameters and try again later. Contact support if the issue persists."
            )


class PartnerIntegrationInactiveClientException(Exception):
    """Custom exception for inactive API clients."""

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = "The API client is inactive. Please contact support to reactivate the client."


class PartnerIntegrationCourseOwnerException(Exception):
    """Custom exception for internal errors during data access."""

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = "You are not allowed to get information about this course."


class PartnerIntegrationEnrollmentPreventedException(Exception):
    """
    Custom exception for filter-based enrollment rejections.

    Raised when an Open edX enrollment filter (e.g., FilterSSOPartnerAccountLink)
    prevents enrollment via CourseEnrollmentStarted.PreventEnrollment.
    """

    def __init__(self, message=None):
        if message:
            self.message = message
        else:
            self.message = (
                "Enrollment was prevented by the enrollment filter pipeline. "
                "Please verify the user's account configuration."
            )
