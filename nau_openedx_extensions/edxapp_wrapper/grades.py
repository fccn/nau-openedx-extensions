""" Grades backend abstraction """
from __future__ import absolute_import, unicode_literals

from importlib import import_module

from django.conf import settings


def get_course_grades(*args, **kwargs):
    """ Gets course grades for a given student """

    backend_module = settings.NAU_GRADES_MODULE
    backend = import_module(backend_module)

    return backend.get_course_grades(*args, **kwargs)
