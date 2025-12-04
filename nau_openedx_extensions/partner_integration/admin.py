"""Admin implementation for PartnerAPIClient"""
import json
import uuid

from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from django.utils.html import format_html

from .models import PartnerAPIClient


class PartnerAPIClientForm(forms.ModelForm):
    """Admin form for better manage PartnerAPIClient registers"""
    query_security_scope = forms.JSONField(
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 10,
            "cols": 80,
            "placeholder": json.dumps({
                "base_security_scope": {
                    "org": "FCCN",
                },
                "base_certificates_scope": {
                    "created_date__gte": "2024-06-01",
                    "user_nauuserextendedmodel__nif__isnull": False,
                    "user_nauuserextendedmodel__cc_nif__isnull": False
                }
            }, indent=2)
        })
    )

    class Meta:
        model = PartnerAPIClient
        fields = "__all__"


@admin.register(PartnerAPIClient)
class PartnerAPIClientAdmin(admin.ModelAdmin):
    """Admin registration for PartnerAPIClient model"""
    form = PartnerAPIClientForm
    list_display = ('name', 'client_id', 'is_active', 'is_staff', 'created_at', 'updated_at')
    readonly_fields = ('client_id', 'created_at', 'updated_at', 'credentials_preview')

    fieldsets = (
        (None, {
            'fields': ('name', 'credentials_preview', 'is_active', 'is_staff', 'query_security_scope')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
        ('Permissions', {
            'fields': ('groups', 'user_permissions'),
        }),
    )

    def credentials_preview(self, obj):
        """
        Display a one-time raw password and UUID for new objects.
        """
        if not obj.pk:
            self._raw_password = get_random_string(64)  # pylint: disable=attribute-defined-outside-init
            self._uuid = uuid.uuid4()  # pylint: disable=attribute-defined-outside-init
            return format_html(
                "<b>Client ID:</b> {}<br><b>Password:</b> {} (copy these before saving!)",
                self._uuid, self._raw_password
            )
        return format_html("<i>Already saved — password hidden</i>")

    credentials_preview.short_description = "Credentials"

    def save_model(self, request, obj, form, change):
        """
        Assign `client_id` and `password` for new objects.
        """
        if not obj.pk:
            obj.client_id = self._uuid
            obj.password = make_password(self._raw_password)
        super().save_model(request, obj, form, change)
