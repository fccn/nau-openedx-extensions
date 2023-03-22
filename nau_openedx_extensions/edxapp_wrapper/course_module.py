""" CourseMetadata backend abstraction """

from importlib import import_module

from django.conf import settings


def get_other_course_settings(*args, **kwargs):
    """ Get Other Course Settings """
    backend_module = settings.NAU_COURSE_MODULE
    backend = import_module(backend_module)

    return backend.get_other_course_settings(*args, **kwargs)


def get_course_name(*args, **kwargs):
    """ Get course name """
    backend_module = settings.NAU_COURSE_MODULE
    backend = import_module(backend_module)

    return backend.get_course_name(*args, **kwargs)
