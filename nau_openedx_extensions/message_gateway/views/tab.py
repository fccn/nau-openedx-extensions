"""
Custom tab for nau message gateway integration
"""
from __future__ import absolute_import, unicode_literals

import logging

import six
from django.http import Http404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_noop
from web_fragments.fragment import Fragment

from nau_openedx_extensions.edxapp_wrapper.fragments import (
    get_course_tab_view,
    get_edx_fragment_view,
    get_enrolled_tab,
    get_tab_fragment_view_mixin,
)
from nau_openedx_extensions.permissions import NAU_SEND_MESSAGE_PERMISSION_NAME

CourseTabView = get_course_tab_view()
EnrolledTab = get_enrolled_tab()
EdxFragmentView = get_edx_fragment_view()
TabFragmentViewMixin = get_tab_fragment_view_mixin()

log = logging.getLogger(__name__)


class NauMessageGatewayTab(TabFragmentViewMixin, EnrolledTab):
    """
    Custom tab for NAU message gateway service.
    """

    type = "message_gw"
    name = "message_gw"
    title = gettext_noop("NAU Message Gateway")
    view_name = "nau-openedx-extensions:nau_tools"
    fragment_view_name = "nau_openedx_extensions.course_tab.views.NauToolsFragmentView"
    is_dynamic = True

    @classmethod
    def is_enabled(cls, course, user=None):  # pylint: disable=unused-argument
        """
        Only available for the users with the NAU_SEND_MESSAGE_PERMISSION_NAME permission.
        """
        return bool(user and user.has_perm(NAU_SEND_MESSAGE_PERMISSION_NAME))

    def uses_bootstrap(self):
        """
        Load this tab with bootstrap enabled.
        """
        return True


class NauToolsFragmentView(EdxFragmentView):
    """
    Fragment view for message gateway tab.
    """
    def render_to_fragment(self, request, course_id):
        """
        Render the message gateway template.
        """
        context = {
            "send_message_endpoint": reverse(
                "nau-openedx-extensions:send_message",
                kwargs={"course_id": six.text_type(course_id)},
            ),
        }
        html = render_to_string("message_gateway/tab.html", context)
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
        If and only if the user has the NAU_SEND_MESSAGE_PERMISSION_NAME permission.
        """
        user = request.user

        if not user.has_perm(NAU_SEND_MESSAGE_PERMISSION_NAME):
            log.info(
                "User <%s> tried to access the Nau Message Gateway Tab in course %s, but they don't "
                "have permission to access that view.",
                user,
                course_id,
            )
            raise Http404()
        return super().get(request, course_id, "message_gw", **kwargs)

    def render_to_fragment(
        self, request, course=None, tab=None, page_context=None, **kwargs  # pylint: disable=unused-argument
    ):
        """
        Fragment for this tab.
        """
        course_id = six.text_type(course.id)
        nau_fragment_view = NauToolsFragmentView()
        return nau_fragment_view.render_to_fragment(
            request, course_id=course_id, **kwargs
        )
