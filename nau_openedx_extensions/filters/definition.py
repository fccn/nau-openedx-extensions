"""Filters definition module."""

from openedx_filters.exceptions import OpenEdxFilterException
from openedx_filters.tooling import OpenEdxPublicFilter

from django.db.models.query import QuerySet


class ScheduleQuerysetRequested(OpenEdxPublicFilter):
    """
    Custom class used to create schedule queryset filters filters and its custom methods.
    """

    filter_type = "org.openedx.learning.schedule.queryset.requested.v1"

    class PreventScheduleQuerysetRequest(OpenEdxFilterException):
        """
        Custom class used to stop the schedule queryset request process.
        """

    @classmethod
    def run_filter(cls, schedules: QuerySet) -> QuerySet:
        """
        Execute a filter with the signature specified.

        Arguments:
            schedules (QuerySet): Queryset of schedules to be sent.
        """
        data = super().run_pipeline(schedules=schedules)
        return data.get("schedules")
