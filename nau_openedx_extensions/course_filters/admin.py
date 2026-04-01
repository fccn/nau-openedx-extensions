"""
Admin configuration for course_filters.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import NauCourseFilter


@admin.register(NauCourseFilter)
class NauCourseFilterAdmin(admin.ModelAdmin):
    """Admin for NauCourseFilter model."""

    list_display = ("course_id", "filter_type", "created_at", "updated_at")
    list_filter = ("filter_type", "created_at")
    search_fields = ("course_id", "filter_type")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("course_id", "filter_type")

    fieldsets = (
        (None, {
            "fields": ("course_id", "filter_type"),
        }),
        (_("Timestamps"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
