""" urls.py """

from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.urls import re_path

from nau_openedx_extensions.message_gateway.views import api as message_gateway_api
from nau_openedx_extensions.message_gateway.views import tab as message_gateway_tab

urlpatterns = [
    re_path(
        r"^nau-tools/{}/$".format(
            settings.COURSE_ID_PATTERN,
        ),
        message_gateway_tab.NauMessageGatewayTabView.as_view(),
        name="nau_tools",
    ),
    re_path(
        r"^nau-tools/{}/send-message$".format(
            settings.COURSE_ID_PATTERN,
        ),
        message_gateway_api.send_message,
        name="send_message",
    ),
]
