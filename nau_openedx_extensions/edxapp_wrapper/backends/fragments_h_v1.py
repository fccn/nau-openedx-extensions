"""
openedx backend for edx fragments
"""
from lms.djangoapps.courseware.tabs import EnrolledTab  # pylint: disable=import-error
from lms.djangoapps.courseware.views.views import CourseTabView  # pylint: disable=import-error
from openedx.core.djangoapps.plugin_api.views import EdxFragmentView  # pylint: disable=import-error
from xmodule.tabs import TabFragmentViewMixin  # pylint: disable=import-error


def get_course_tab_view():
    return CourseTabView


def get_edx_fragment_view():
    return EdxFragmentView


def get_tab_fragment_view_mixin():
    return TabFragmentViewMixin


def get_enrolled_tab():
    return EnrolledTab
