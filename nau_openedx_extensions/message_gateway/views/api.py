"""
APIs for message gateway integration.
"""
from __future__ import absolute_import, unicode_literals

import json
import logging

import six
from common.djangoapps.util.json_request import JsonResponse  # pylint: disable=import-error
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponseBadRequest
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.message_gateway import tasks
from nau_openedx_extensions.message_gateway.models import NauCourseMessage
from nau_openedx_extensions.permissions import NAU_SEND_MESSAGE_PERMISSION_NAME

log = logging.getLogger(__name__)


@require_POST
@ensure_csrf_cookie
@permission_required(NAU_SEND_MESSAGE_PERMISSION_NAME)
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def send_message(request, course_id):
    """
    Create subtasks to send bulk messages using NAU message gateway.
    """
    course_key = CourseKey.from_string(course_id)

    targets = json.loads(request.POST.get("send_to"))
    message = request.POST.get("message")

    try:
        message = NauCourseMessage.create(
            course_key,
            request.user,
            message,
            targets,
        )
    except ValueError as err:
        return HttpResponseBadRequest(repr(err))

    tasks.submit_bulk_course_message.delay(message_id=message.id, course_id=course_id)
    log.info(
        "Task to submit course messages was successfuly created with course message id (%d)",
        message.id,
    )

    response_payload = {
        "course_id": six.text_type(course_id),
        "success": True,
    }
    return JsonResponse(response_payload)
