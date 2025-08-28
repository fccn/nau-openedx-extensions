"""
Admin configuration for enrollment_by_domain app.

This module contains Django admin configurations for:
- EnrollmentAllowedList: Lists of allowed domains for course enrollment
- EnrollmentAllowedDomain: Individual domains within allowed lists
"""

from django.contrib import admin
from django.db import models
from django.forms import Textarea
from django.utils.translation import gettext_lazy as _

from nau_openedx_extensions.utils.admin import ExportCsvMixin

from .models import EnrollmentAllowedDomain, EnrollmentAllowedList


class EnrollmentAllowedDomainInline(admin.TabularInline):
    """Inline for managing domains within an allowed list."""
    model = EnrollmentAllowedDomain
    extra = 3
    fields = ('domain',)
    verbose_name = _("Allowed Domain")
    verbose_name_plural = _("Allowed Domains")

    formfield_overrides = {
        models.CharField: {'widget': Textarea(attrs={'rows': 1, 'cols': 40})},
    }


@admin.register(EnrollmentAllowedList)
class EnrollmentAllowedListAdmin(admin.ModelAdmin, ExportCsvMixin):
    """Admin for EnrollmentAllowedList model."""
    list_display = ('code', 'description_short', 'domain_count', 'has_custom_message', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('code', 'description')
    readonly_fields = ('created_at', 'updated_at', 'domain_count')
    inlines = [EnrollmentAllowedDomainInline]

    actions = ['export_as_csv', 'duplicate_selected']

    csv_export_fields = ('code', 'description', 'custom_exception_message', 'created_at', 'updated_at')

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('code', 'description')
        }),
        (_('Custom Message'), {
            'fields': ('custom_exception_message',),
            'description': _('This message has priority 2. Course settings have priority 1.')
        }),
        (_('Statistics'), {
            'fields': ('domain_count',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 80})},
    }

    def description_short(self, obj):
        """Return shortened description."""
        if not obj.description:
            return '-'
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
    description_short.short_description = _('Description')

    def domain_count(self, obj):
        """Return count of domains in this list."""
        return obj.domains.count()
    domain_count.short_description = _('Domain Count')
    domain_count.admin_order_field = 'domains__count'

    def has_custom_message(self, obj):
        """Return whether this list has a custom message."""
        return bool(obj.custom_exception_message)
    has_custom_message.short_description = _('Custom Message')
    has_custom_message.boolean = True

    def get_queryset(self, request):
        """Optimize queryset with annotations."""
        return super().get_queryset(request).prefetch_related('domains')

    def duplicate_selected(self, request, queryset):
        """Action to duplicate selected allowed lists."""
        duplicated_count = 0
        for obj in queryset:
            # Get original domains
            original_domains = list(obj.domains.values_list('domain', flat=True))

            # Create duplicate
            obj.pk = None
            obj.code = f"{obj.code}_copy"
            obj.save()

            # Create domains for the duplicate
            for domain in original_domains:
                EnrollmentAllowedDomain.objects.create(
                    allowed_list=obj,
                    domain=domain
                )
            duplicated_count += 1

        self.message_user(
            request,
            _('Successfully duplicated %(count)d allowed list(s).') % {'count': duplicated_count}
        )
    duplicate_selected.short_description = _('Duplicate selected allowed lists')


@admin.register(EnrollmentAllowedDomain)
class EnrollmentAllowedDomainAdmin(admin.ModelAdmin, ExportCsvMixin):
    """Admin for EnrollmentAllowedDomain model."""
    list_display = ('domain', 'allowed_list', 'created_at')
    list_filter = ('allowed_list', 'created_at')
    search_fields = ('domain', 'allowed_list__code', 'allowed_list__description')
    readonly_fields = ('created_at',)
    list_select_related = ('allowed_list',)

    actions = ['export_as_csv']

    csv_export_fields = ('domain', 'allowed_list', 'created_at')

    fieldsets = (
        (None, {
            'fields': ('allowed_list', 'domain')
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('allowed_list')
