"""Admin implementation for PartnerAPIClient"""
import json
import logging

from common.djangoapps.util.query import use_read_replica_if_available  # lint-amnesty, pylint: disable=import-error
from django import forms
from django.contrib import admin
from django.utils.crypto import get_random_string

from .models import PartnerAPIClient, SSOPartnerIntegration

logger = logging.getLogger(__name__)


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


@admin.register(SSOPartnerIntegration)
class SSOPartnerIntegrationAdmin(admin.ModelAdmin):
    """Admin registration for SSOPartnerIntegration model"""
    list_display = (
        'user',
        'openedx_email',
        'partner_client',
        'external_user_id',
        'created_at',
        'updated_at',
    )
    list_filter = ('partner_client',)
    raw_id_fields = ('user',)
    search_fields = (
        'user__username',
        'user__email',
        'user__id',
        'external_user_id',
        'partner_client__name',
    )
    search_help_text = "Search by user username, email or id"
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('user', 'partner_client')

    fieldsets = (
        (None, {
            'fields': ('partner_client', 'user', 'external_user_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def openedx_email(self, instance):
        """Read only method to see the user's email"""
        try:
            return instance.user.email
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Error occurred while fetching user email: %s", str(error))
            return str(error)

    def get_search_results(self, request, queryset, search_term):
        """Override the default search to apply `use_read_replica_if_available`"""
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        return use_read_replica_if_available(qs), use_distinct
