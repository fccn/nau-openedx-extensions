""" Grades backend abstraction """
from importlib import import_module
from django.conf import settings


def get_course_grades(*args, **kwargs):
    """ Gets course grades for a given student """

    backend_module = settings.GRADES_MODULE
    backend = import_module(backend_module)

    return backend.get_course_grades(*args, **kwargs)
