"""Filters definition module."""

from openedx_filters.exceptions import OpenEdxFilterException
from openedx_filters.tooling import OpenEdxPublicFilter


class ScheduleNudgeEmailStarted(OpenEdxPublicFilter):
    """
    Custom class used to create schedule email filters and its custom methods.
    """

    filter_type = "org.openedx.learning.schedule.nudge.email.started.v1"

    class InvalidSchedule(OpenEdxFilterException):
        """
        Custom class used to stop the submission view render process.
        """

        def __init__(self, message: str, schedules):
            """
            Override init that defines specific arguments used in the submission view render process.

            Arguments:
                message (str): error message for the exception.
                schedules (QuerySet): schedules to be sent.
            """
            super().__init__(message, schedules=schedules)

    @classmethod
    def run_filter(cls, schedules):
        """
        Execute a filter with the signature specified.

        Arguments:
            schedules (QuerySet): Queryset of schedules to be sent.
        """
        data = super().run_pipeline(schedules=schedules)
        return data.get("schedules")
