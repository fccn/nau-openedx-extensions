"""
Django models for the message gateway integration
"""
from __future__ import absolute_import, unicode_literals

import logging

from bulk_email.models import EMAIL_TARGETS, Target  # pylint: disable=import-error
from django.contrib.auth.models import User
from django.db import models
from opaque_keys.edx.django.models import CourseKeyField

log = logging.getLogger(__name__)


class NauCourseMessage(models.Model):
    """
    Model that stores the information of the messages that are sent by the Nau Message Gateway.
    """

    sender = models.ForeignKey(
        User, default=1, blank=True, null=True, on_delete=models.CASCADE
    )
    course_id = CourseKeyField(max_length=255, db_index=True)
    targets = models.ManyToManyField(Target)
    message = models.TextField(null=True, blank=True)

    @classmethod
    def create(cls, course_id, sender, message, targets):
        """
        Create NauCourseMessage instance and store it in the DB
        """
        new_targets = []
        for target in targets:
            # split target, to handle cohort:cohort_name and track:mode_slug
            target_split = target.split(":", 1)
            # Ensure our desired target exists
            if target_split[0] not in EMAIL_TARGETS:
                fmt = 'Course message being sent to unrecognized target: "{target}" for "{course}"'
                msg = fmt.format(target=target, course=course_id)
                log.info(msg)
                raise ValueError(msg)
            else:
                new_target, _ = Target.objects.get_or_create(
                    target_type=target_split[0]
                )
            new_targets.append(new_target)

        # create the task, then save it immediately:
        course_message = cls(
            course_id=course_id,
            sender=sender,
            message=message,
        )
        course_message.save()  # Must exist in db before setting M2M relationship values
        course_message.targets.add(*new_targets)
        course_message.save()

        return course_message

    def __unicode__(self):
        return "<Nau Course Message from course {} with id {}>".format(self.course_id, self.id)
