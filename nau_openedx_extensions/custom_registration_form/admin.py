"""
Admin for nau user extended model
"""

from __future__ import absolute_import, unicode_literals

from common.djangoapps.util.query import use_read_replica_if_available  # lint-amnesty, pylint: disable=import-error
from django.contrib import admin

from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel
from nau_openedx_extensions.utils.admin import ExportCsvMixin


@admin.register(NauUserExtendedModel)
class NauUserExtendedModelAdmin(admin.ModelAdmin, ExportCsvMixin):
    """
    Helper model to make administration of many such models easier.
    """

    search_fields = (
        "user__email",
        "user__username",
    )
    readonly_fields = (
        "openedx_username",
        "openedx_email",
    )
    raw_id_fields = ("user",)
    list_filter = ("allow_newsletter", "user__date_joined")
    list_display = ("openedx_username", "openedx_email", "date_joined")

    # use this user date_joined field has an hierarchy to the user can search the last registries more rapid.
    date_hierarchy = "user__date_joined"

    # limit the fields that are exported to CSV to prevent export a CSV with information too personal like NIC
    csv_export_fields = ("user", "openedx_email", "data_authorization",
                         "employment_situation", "allow_newsletter", "date_joined",)

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

    def get_search_results(self, request, queryset, search_term):
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term and len(search_term) > 0 and len(search_term) < 3:
            qs = NauUserExtendedModel.objects.none()
        return use_read_replica_if_available(qs), use_distinct
