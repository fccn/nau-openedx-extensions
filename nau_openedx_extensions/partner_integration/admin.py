"""Admin implementation for PartnerAPIClient"""
import json

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
        help_text="Enter a valid JSON object. Example: {\"base_security_scope\": {\"org\": \"NAU\"}}",
        widget=forms.Textarea(attrs={
            "rows": 10,
            "cols": 80,
            "placeholder": json.dumps({
                "base_security_scope": {
                    "org": "NAU",
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
            obj.password = get_random_string(64)  # pylint: disable=attribute-defined-outside-init
            return format_html(
                "<b>Secret:</b> {}<br><b>Copy before saving!</b>",
                obj.password
            )
        return format_html("<b>Client ID:</b> {}<br><b>Secret:</b> <i>Already saved, it's hidden</i>", obj.client_id)

    credentials_preview.short_description = "Secret"

    def save_model(self, request, obj, form, change):
        """
        Assign `client_id` and `password` for new objects.
        """
        if not obj.pk:
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)
