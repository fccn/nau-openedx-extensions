"""Admin implementation for PartnerAPIClient"""
from django.contrib import admin
from django.utils.html import format_html

from .models import PartnerAPIClient


@admin.register(PartnerAPIClient)
class PartnerAPIClientAdmin(admin.ModelAdmin):
    """
    Admin interface for PartnerAPIClient, allows managing API clients.
    """
    list_display = (
        "id",
        "name",
        "client_id",
        "is_active",
        "is_staff",
        "created_at",
        "updated_at",
        "preview_security_scope",
    )

    list_filter = ("is_active", "is_staff", "created_at")
    search_fields = ("name", "client_id")
    readonly_fields = ("client_id", "password", "created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": (
                "name",
                "client_id",
                "password",
                "is_active",
                "is_staff",
                "query_security_scope",
            )
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
        ("Permissions", {
            "classes": ("collapse",),
            "fields": (
                "groups",
                "user_permissions",
            )
        }),
    )

    def preview_security_scope(self, obj):
        """
        Small human-readable preview of the security scope JSON.
        """
        if not obj.query_security_scope:
            return "-"

        text = str(obj.query_security_scope)
        preview = text[:80] + ("..." if len(text) > 80 else "")

        return format_html("<code>{}</code>", preview)

    preview_security_scope.short_description = "Security Scope"
