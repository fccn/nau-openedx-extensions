"""
Extension of course access role admin screen with export to csv action
"""
from django.contrib import admin
from .models import CourseAccessRoleProxy
#from common.djangoapps.student.admin import CourseAccessRoleAdmin
from nau_openedx_extensions.utils.admin import ExportCsvMixin

@admin.register(CourseAccessRoleProxy)
class CourseAccessRoleProxyAdmin(admin.ModelAdmin, ExportCsvMixin):
    list_display = ('id', 'user', 'openedx_email', 'org', 'course_id', 'role',)

    # Add a new action to combo box that permit to export to csv the selected rows
    actions = ["export_as_csv"]

    # redefine so email is included
    csv_export_fields = ('id', 'user', 'openedx_email', 'org', 'course_id', 'role',)

    def has_add_permission(self, request, obj=None):
        """
        Disable add functionality 
        """
        return False

    def has_change_permission(self, request, obj=None):
        """
        Disable change/edit functionality 
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Disable change/edit functionality 
        """
        return False

    def openedx_email(self, instance):
        """
        Read only method to see ther users email
        """
        # pylint: disable=broad-except
        try:
            return instance.user.email
        except Exception as error:
            return str(error)
