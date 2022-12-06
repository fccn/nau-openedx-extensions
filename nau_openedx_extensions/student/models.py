"""
Proxy the CourseAccessRole class, so we can generate a different admin screen.
To generate a csv with all course access roles.
"""
from common.djangoapps.student.models import CourseAccessRole # lint-amnesty, pylint: disable=import-error

class CourseAccessRoleProxy(CourseAccessRole):

    class Meta:
        proxy = True
