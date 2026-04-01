"""
Models for course_filters app.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class NauCourseFilter(models.Model):
    """
    Stores which enrollment/certificate filters are active for a given course.

    Each row represents one active filter on one course. The table is kept in
    sync with MongoDB's other_course_settings on every course publish so that
    the nau-database-exporter can query filter status from MySQL without
    touching MongoDB.
    """

    course_id = models.CharField(
        max_length=255,
        help_text=_("Course key string (e.g. course-v1:ORG+ID+Run)"),
        verbose_name=_("Course ID"),
        db_index=True,
    )
    filter_type = models.CharField(
        max_length=255,
        help_text=_(
            "Filter key name as stored in other_course_settings "
            "(e.g. filter_enrollment_by_domain_list, filter_enrollment_require_nif, "
            "certificate_require_portuguese_citizen_card)"
        ),
        verbose_name=_("Filter Type"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "nau_openedx_extensions"
        verbose_name = _("NAU Course Filter")
        verbose_name_plural = _("NAU Course Filters")
        unique_together = [("course_id", "filter_type")]
        ordering = ["course_id", "filter_type"]

    def __str__(self):
        return f"{self.course_id}: {self.filter_type}"
