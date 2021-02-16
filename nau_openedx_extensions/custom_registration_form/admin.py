"""
Admin for nau user extended model
"""

from __future__ import absolute_import, unicode_literals
from django.contrib import admin
from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel

# imports related with export to Csv
import csv
from django.http import HttpResponse

import datetime

class ExportCsvMixin:
    """
    Generic mixin that has an admin action that exports its data to CSV
    optionally the ModelAdmin instance can define a tuple "csv_export_fields" with specific fields or functions to export
    """
    def export_as_csv(self, request, queryset):
        opts = self.model._meta
        orm_fields = opts.get_fields()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(opts.verbose_name.replace(' ','_'))
        writer = csv.writer(response)

        def transform_field(csv_field):
            for field in orm_fields:
                if not field.many_to_many and not field.one_to_many:
                    if field.name == csv_field:
                        return field
            return csv_field

        fields = list(map(transform_field, list(self.csv_export_fields)) if hasattr(self, 'csv_export_fields') else orm_fields)

        print(str(fields))

        # Write a first row with header information
        writer.writerow([field.verbose_name if hasattr(field, 'verbose_name') else str(field) for field in fields])
        # Write data rows
        for obj in queryset:
            data_row = []
            for field in fields:
                if not isinstance(field, str):
                    field = field.name
                value = getattr(obj, field)
                if callable(value):
                    value = value()
                if isinstance(value, datetime.datetime):
                    value = value.strftime('%Y-%m-%d')
                data_row.append(value)
            writer.writerow(data_row)

        return response


    export_as_csv.short_description = "Export Selected"

@admin.register(NauUserExtendedModel)
class NauUserExtendedModelAdmin(admin.ModelAdmin, ExportCsvMixin):
    """
    Helper model to make administration of many such models easier.
    """

    search_fields = (
        "user__email",
        "user__username",
        "cc_nif",
        "cc_first_name",
        "cc_last_name",
    )
    readonly_fields = (
        "openedx_username",
        "openedx_email",
    )
    raw_id_fields = ("user",)
    list_filter = ("allow_newsletter", "user__date_joined")
    list_display = ("openedx_username", "openedx_email", "date_joined")

    # use this user date_joined field has an hierarchy to the user can search the last registries more rapid.
    date_hierarchy= "user__date_joined"
    
    # limit the fields that are exported to CSV to prevent export a CSV with information too personal like NIC
    csv_export_fields = ("user", "data_authorization", "employment_situation", "allow_newsletter", "date_joined",)

    # Add a new action to combo box that permit to export to csv the selected rows
    actions = ["export_as_csv"]

    def openedx_email(self, instance):
        """
        Read only method to see ther users email
        """
        # pylint: disable=broad-except
        try:
            return instance.user.email
        except Exception as error:
            return str(error)

    def openedx_username(self, instance):
        """
        Read only method to see ther users username
        """
        # pylint: disable=broad-except
        try:
            return instance.user.username
        except Exception as error:
            return str(error)

