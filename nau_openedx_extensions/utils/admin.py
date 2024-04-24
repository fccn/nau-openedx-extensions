"""
NAU admin extension
"""
import csv
import datetime

from common.djangoapps.util.query import use_read_replica_if_available  # lint-amnesty, pylint: disable=import-error
from django.http import HttpResponse


class ExportCsvMixin:
    """
    Generic mixin that has an admin action that exports its data to CSV
    optionally the ModelAdmin instance can define a tuple "csv_export_fields"
    with specific fields or functions to export
    """

    def export_as_csv(self, request, queryset):
        """
        Export as csv file.
        """
        opts = self.model._meta
        orm_fields = opts.get_fields()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}.csv'.format(opts.verbose_name.replace(' ', '_'))
        writer = csv.writer(response)

        def transform_field(csv_field):
            for field in orm_fields:
                if not field.many_to_many and not field.one_to_many:
                    if field.name == csv_field:
                        return field
            return csv_field

        fields = list(map(transform_field, list(self.csv_export_fields))
                      if hasattr(self, 'csv_export_fields') else orm_fields)

        print(str(fields))

        # Write a first row with header information
        writer.writerow([field.verbose_name if hasattr(field, 'verbose_name') else str(field) for field in fields])
        # Write data rows
        for obj in use_read_replica_if_available(queryset):
            data_row = []
            for field in fields:
                if not isinstance(field, str):
                    field = field.name
                if hasattr(obj, field):
                    value = getattr(obj, field)
                else:
                    func = getattr(self, field)
                    value = func(obj)
                if callable(value):
                    value = value()
                if isinstance(value, datetime.datetime):
                    value = value.strftime('%Y-%m-%d')
                data_row.append(value)
            writer.writerow(data_row)

        return response

    export_as_csv.short_description = "Export Selected"
