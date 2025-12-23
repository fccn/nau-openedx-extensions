"""Admin implementation for PartnerAPIClient"""
import json

from django import forms
from django.contrib import admin
from django.utils.crypto import get_random_string

from .models import PartnerAPIClient


class PartnerAPIClientForm(forms.ModelForm):
    """Admin form for better manage PartnerAPIClient registers"""
    password = forms.CharField(
        required=True,
        label="Secret",
        help_text="The password field of PartnerAPIClient model",
        widget=forms.TextInput(attrs={"size": 80})
    )
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
    readonly_fields = ('client_id', 'created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'password', 'is_active', 'is_staff', 'query_security_scope')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
        ('Permissions', {
            'fields': ('groups', 'user_permissions'),
        }),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        current_form = super().get_form(request, obj, **kwargs)
        if not obj:
            current_form.base_fields["password"].initial = get_random_string(64)
        return current_form
