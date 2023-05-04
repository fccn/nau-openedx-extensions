"""
Extension of course access role admin screen with export to csv action
"""
from common.djangoapps.student.admin import (  # lint-amnesty, pylint: disable=import-error
    CourseAccessRoleAdmin,
    CourseEnrollmentForm,
    DisableEnrollmentAdminMixin,
)
from common.djangoapps.student.models import (  # lint-amnesty, pylint: disable=import-error
    CourseAccessRole,
    CourseEnrollment,
)
from common.djangoapps.util.query import use_read_replica_if_available  # lint-amnesty, pylint: disable=import-error
from django.contrib import admin

from nau_openedx_extensions.utils.admin import ExportCsvMixin

# Unregister the default Django Admin screen for CourseAccessRole class.
admin.site.unregister(CourseAccessRole)


@admin.register(CourseAccessRole)
class NAUCourseAccessRoleAdmin(CourseAccessRoleAdmin, ExportCsvMixin):
    """
    NAU custom Admin screen for the class of openedx CourseAccessRole.
    Improve with:
      1. export to csv
      2. add user email to the user interface
      3. add filter by role and organization
    """
    list_display = ('id', 'user', 'openedx_email', 'org', 'course_id', 'role',)
    list_filter = [
        ('role'),
        ('org'),
        # ('course_id', admin.EmptyFieldListFilter), # need minimum Django 3.1
    ]

    # Add a new action to combo box that permit to export to csv the selected rows
    actions = ["export_as_csv"]

    # redefine so email is included
    csv_export_fields = ('id', 'user', 'openedx_email', 'org', 'course_id', 'role',)

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
admin.site.unregister(CourseEnrollment)


# Register the custom NAU Django Admin screen for CourseEnrollment class
# Changes from upstream:
# - remove the custom order by / sort;
# - remove the select_related user;
# - search only if search term has minimum 3 characters length;
# - change search by user username or email;
# - use `read_replica` database if available for search;
@admin.register(CourseEnrollment)
class NAUCourseEnrollmentAdmin(DisableEnrollmentAdminMixin, admin.ModelAdmin):
    """
    NAU custom admin interface for the CourseEnrollment model.
    The upstream version has performance problems.
    """
    list_display = ('id', 'user', 'email', 'course_id', 'mode', 'is_active',)
    list_filter = ('mode', 'is_active',)
    raw_id_fields = ('user',)
    search_fields = ('user__username', 'user__email')
    form = CourseEnrollmentForm
    search_help_text = "Search by user username or email"

    def email(self, obj):
        return obj.user.email

    def get_search_results(self, request, queryset, search_term):
        qs, use_distinct = super().get_search_results(request, queryset, search_term)
        if not search_term or len(search_term) < 3:
            qs = CourseEnrollment.objects.none()
        return use_read_replica_if_available(qs), use_distinct
