import six
import logging

from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import ugettext_noop
from django.http import Http404, HttpResponseServerError

from opaque_keys.edx.keys import CourseKey
from opaque_keys import InvalidKeyError
from web_fragments.fragment import Fragment

from nau_openedx_extensions.edxapp_wrapper.courseware import get_has_access, get_get_course_by_id
from nau_openedx_extensions.edxapp_wrapper.fragments import (
    get_course_tab_view,
    get_enrolled_tab,
    get_edx_fragment_view,
    get_tab_fragment_view_mixin
)

CourseTabView = get_course_tab_view()
EnrolledTab = get_enrolled_tab()
EdxFragmentView = get_edx_fragment_view()
TabFragmentViewMixin = get_tab_fragment_view_mixin()
get_course_by_id = get_get_course_by_id()
has_access = get_has_access()

log = logging.getLogger(__name__)


class NauMessageGatewayTab(TabFragmentViewMixin, EnrolledTab):
    """
    Custom tab for NAU message gateway service.
    """
    type = 'message_gw'
    name = "message_gw"
    title = ugettext_noop("NAU Message Gateway")
    view_name = "nau-openedx-extensions:nau_tools"
    fragment_view_name = "nau_openedx_extensions.course_tab.views.NauToolsFragmentView"
    is_dynamic = True

    @classmethod
    def is_enabled(cls, course, user=None):
        """
        Only available for the Course Staff
        """
        return bool(user and has_access(user, 'staff', course, course.id))

    def uses_bootstrap(self):
        """
        Load this tab with bootstrap enabled.
        """
        return True

class NauToolsFragmentView(EdxFragmentView):
    def render_to_fragment(self, request, course_id):
        """
        """
        context = {
            "send_message_endpoint": reverse('nau-openedx-extensions:send_message',
                                             kwargs={'course_id': six.text_type(course_id)}),
        }
        html = render_to_string('message_gateway/tab.html', context)
        fragment = Fragment(html)
        self.add_fragment_resource_urls(fragment)

        return fragment

    def js_dependencies(self):
        """
        Use custom js files.
        """
        return ["nau_openedx_extensions/js/send_message.js"]

    def css_dependencies(self):
        """
        Use custom css files.
        """
        return ["nau_openedx_extensions/css/send_message.css", "css/lms-course.css"]


class NauMessageGatewayTabView(CourseTabView):
    """
    The NAU course message page.
    """

    def get(self, request, course_id, **kwargs):
        """
        Displays a the course message tab page that contains a web fragment.
        If and only if the user has staff access to the course.
        """
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return HttpResponseServerError()

        course = get_course_by_id(course_key, depth=0)

        is_course_staff = has_access(request.user, 'staff', course)

        if not is_course_staff:
            log.info("User <%s> tried to access the Nau Message Gateway Tab, but they don't "
                     "have staff access to the course %s", request.user, course_id)
            raise Http404()
        return super(NauMessageGatewayTabView, self).get(request, course_id, 'message_gw', **kwargs)

    def render_to_fragment(self, request, course=None, tab=None, page_context=None, **kwargs):
        """
        Fragment for this tab.
        """
        course_id = six.text_type(course.id)
        nau_fragment_view = NauToolsFragmentView()
        return nau_fragment_view.render_to_fragment(request, course_id=course_id, **kwargs)
