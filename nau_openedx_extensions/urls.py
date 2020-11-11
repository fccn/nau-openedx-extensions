""" urls.py """

from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.conf.urls import url

from nau_openedx_extensions.message_gateway.views import api as message_gateway_api
from nau_openedx_extensions.message_gateway.views import tab as message_gateway_tab

urlpatterns = [
    url(
        r"^nau-tools/{}/$".format(
            settings.COURSE_ID_PATTERN,
        ),
        message_gateway_tab.NauMessageGatewayTabView.as_view(),
        name="nau_tools",
    ),
    url(
        r"^nau-tools/{}/send-message$".format(
            settings.COURSE_ID_PATTERN,
        ),
        message_gateway_api.send_message,
        name="send_message",
    ),
]
