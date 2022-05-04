from common.djangoapps.student.models import CourseAccessRole

class CourseAccessRoleProxy(CourseAccessRole):

    class Meta:
        proxy = True
