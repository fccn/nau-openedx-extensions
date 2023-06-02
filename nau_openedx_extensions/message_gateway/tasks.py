"""
Async tasks for the message gateway integration.
"""
from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task  # lint-amnesty, pylint: disable=import-error
from django.conf import settings
from django.contrib.auth.models import User  # lint-amnesty, pylint: disable=imported-auth-user
from opaque_keys.edx.keys import CourseKey

from nau_openedx_extensions.message_gateway.backends import get_backend
from nau_openedx_extensions.message_gateway.models import NauCourseMessage

log = logging.getLogger(__name__)


@shared_task
def submit_bulk_course_message(message_id, course_id):
    """
    Submit course messages. This will create the subtasks that submits
    the course messages. Each subtask will send at most
    settings.NAU_COURSE_MESSAGE_BATCH_SIZE messages
    """
    try:
        message_obj = NauCourseMessage.objects.get(id=message_id)
    except NauCourseMessage.DoesNotExist:
        log.error("Not found a NauCourseMessage with id (%d)", message_id)
        raise

    course_key = CourseKey.from_string(course_id)
    if course_key != message_obj.course_id:
        format_msg = (
            "Course id conflict: explicit value %r does not match task value %r"
        )
        log.error(format_msg, course_key, message_obj.course_id)
        raise ValueError(format_msg % (course_id, message_obj.course_id))

    # Get arguments that will be passed to every subtask.
    targets = message_obj.targets.all()
    user_id = message_obj.sender.id

    recipient_qsets = [target.get_users(course_key, user_id) for target in targets]
    combined_set = User.objects.none()
    for qset in recipient_qsets:
        combined_set |= qset
    combined_set = combined_set.distinct()

    total_recipients = combined_set.count()

    if total_recipients == 0:
        msg = "Bulk Course Email Task: Empty recipient set"
        log.error(msg)
        raise ValueError(msg)
    batch_size = getattr(settings, "NAU_COURSE_MESSAGE_BATCH_SIZE", 50)
    for recipients in _iterate_over_recipients(combined_set, batch_size):
        submit_course_message.delay(message_id, recipients)


def _iterate_over_recipients(combined_set, batch_size):
    """
    Iterate over recipients and generate lists of batch_size size.
    """
    recipient_fields = list(
        getattr(settings, "NAU_COURSE_MESSAGE_RECIPIENT_FIELDS", [])
    )
    recipient_fields.append("pk")
    recipients = []
    num_subtasks = 0
    num_items_queued = 0
    for recipient in combined_set.values(*recipient_fields).iterator():
        if len(recipients) == batch_size:
            yield recipients
            num_items_queued += batch_size
            recipients = []
            num_subtasks += 1
        recipients.append(recipient)

        # yield remainder items for task, if any
    if recipients:
        yield recipients
        num_items_queued += len(recipients)


@shared_task
def submit_course_message(message_id, recipients):
    """
    Send course message to the recipients given.
    """
    try:
        message = NauCourseMessage.objects.get(id=message_id)
    except NauCourseMessage.DoesNotExist:  # lint-amnesty, pylint: disable=try-except-raise
        raise

    backend = get_backend()
    backend.send_message(message, recipients)
