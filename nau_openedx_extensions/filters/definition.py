"""Filters definition module."""

from openedx_filters.exceptions import OpenEdxFilterException
from openedx_filters.tooling import OpenEdxPublicFilter

from django.db.models.query import QuerySet


class ScheduleQuerySetRequested(OpenEdxPublicFilter):
    """
    Custom class used to create schedule queryset filters filters and its custom methods.
    """

    filter_type = "org.openedx.learning.schedule.queryset.requested.v1"

    class PreventScheduleQuerysetRequest(OpenEdxFilterException):
        """
        Custom class used to stop the schedule queryset request process.
        """

        def __init__(self, message: str, schedules: QuerySet):
            """
            Override init that defines specific arguments used in the schedule queryset request process.

            Arguments:
                message (str): error message for the exception.
                schedules (QuerySet): Queryset of schedules to be sent
            """
            super().__init__(message, schedules=schedules)

    @classmethod
    def run_filter(cls, schedules: QuerySet) -> QuerySet:
        """
        Execute a filter with the signature specified.

        Arguments:
            schedules (QuerySet): Queryset of schedules to be sent.
        """
        data = super().run_pipeline(schedules=schedules)
        return data.get("schedules")
