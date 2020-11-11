""" Courseware backend abstraction """
from __future__ import absolute_import, unicode_literals

from importlib import import_module

from django.conf import settings


def get_has_access():
    """ Get has_access function from edx-platform"""

    backend_module = settings.NAU_COURSEWARE_MODULE
    backend = import_module(backend_module)

    return backend.get_has_access()


def get_get_course_by_id():
    """ Get get_course_by_id function from edx-platform """

    backend_module = settings.NAU_COURSEWARE_MODULE
    backend = import_module(backend_module)

    return backend.get_get_course_by_id()
