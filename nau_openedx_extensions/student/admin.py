"""
Extension of course access role admin screen with export to csv action
"""
from common.djangoapps.student.admin import (  # lint-amnesty, pylint: disable=import-error
    CourseEnrollmentForm,
    DisableEnrollmentAdminMixin,
)
from common.djangoapps.student.models import CourseEnrollment  # lint-amnesty, pylint: disable=import-error
from django.contrib import admin

from nau_openedx_extensions.utils.admin import ExportCsvMixin

from .models import CourseAccessRoleProxy


@admin.register(CourseAccessRoleProxy)
class CourseAccessRoleProxyAdmin(admin.ModelAdmin, ExportCsvMixin):
    """
    Admin screen for the proxy class of openedx CourseAccessRole.
    """
    list_display = ('id', 'user', 'openedx_email', 'org', 'course_id', 'role',)

    # Add a new action to combo box that permit to export to csv the selected rows
    actions = ["export_as_csv"]

    # redefine so email is included
    csv_export_fields = ('id', 'user', 'openedx_email', 'org', 'course_id', 'role',)

    def has_add_permission(self, request, obj=None):  # lint-amnesty, pylint: disable=unused-argument
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


# Unregister the default Django Admin screen for CourseEnrollment class.
# Because the upstream version has performance problems.
admin.site.unregister(CourseEnrollment)


# Register the custom NAU Django Admin screen for CourseEnrollment class
# Changes from upstream:
# - remove the custom order by / sort;
# - remove the select_related user;
# - change search by user username or email;
@admin.register(CourseEnrollment)
class NAUCourseEnrollmentAdmin(DisableEnrollmentAdminMixin, admin.ModelAdmin):
    """ Admin interface for the CourseEnrollment model. """
    list_display = ('id', 'user', 'email', 'course_id', 'mode', 'is_active',)
    list_filter = ('mode', 'is_active',)
    raw_id_fields = ('user',)
    search_fields = ('user__username', 'user__email')
    form = CourseEnrollmentForm
    search_help_text = "Search by user username or email"

    def email(self, obj):
        return obj.user.email
