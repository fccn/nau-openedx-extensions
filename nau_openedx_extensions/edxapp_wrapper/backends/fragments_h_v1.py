
from lms.djangoapps.courseware.tabs import EnrolledTab
from lms.djangoapps.courseware.views.views import CourseTabView
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView
from xmodule.tabs import TabFragmentViewMixin

def get_course_tab_view(*args, **kwargs):
    return CourseTabView

def get_edx_fragment_view(*args, **kwargs):
    return EdxFragmentView

def get_tab_fragment_view_mixin(*args, **kwargs):
    return TabFragmentViewMixin

def get_enrolled_tab(*args, **kwargs):
    return EnrolledTab

