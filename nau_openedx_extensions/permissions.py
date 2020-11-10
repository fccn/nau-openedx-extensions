#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NAU openedx extensions permissions module
"""
from __future__ import absolute_import, unicode_literals

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.utils import ProgrammingError

NAU_SEND_MESSAGE_PERMISSION_APP_LABEL = "auth"
NAU_SEND_MESSAGE_PERMISSION_CODENAME = "can_send_message"
NAU_SEND_MESSAGE_PERMISSION_NAME = ".".join(
    [
        NAU_SEND_MESSAGE_PERMISSION_APP_LABEL,
        NAU_SEND_MESSAGE_PERMISSION_CODENAME,
    ]
)


def load_permissions():
    """
    Helper method to load a custom permission on DB that will be use to control
    who can send messages using the NAU Message Gateway.
    """
    try:
        content_type = ContentType.objects.get_for_model(get_user_model())
        Permission.objects.get_or_create(
            codename=NAU_SEND_MESSAGE_PERMISSION_CODENAME,
            name="Can send messages using the NAU Message Gateway",
            content_type=content_type,
        )
    except ProgrammingError:
        # This code runs when the app is loaded, if a migration has not been done
        # a ProgrammingError exception is raised we are bypassing those cases to
        # let migrations run smoothly.
        pass
