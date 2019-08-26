from django.contrib import admin
from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel


class NauUserExtendedModelAdmin(admin.ModelAdmin):
    """
    Helper model to make administration of many such models easier.
    """
    search_fields = (
        'user__email',
        'user__username',
        'cc_nif',
        'cc_first_name',
        'cc_last_name',
    )
    readonly_fields = (
        'openedx_username',
        'openedx_email',
    )
    raw_id_fields = ('user',)
    list_display = ('openedx_username', 'openedx_email', 'cc_nif', 'data_authorization')

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


admin.site.register(NauUserExtendedModel, NauUserExtendedModelAdmin)
