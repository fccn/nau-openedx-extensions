""" Fragments backend abstraction """
from importlib import import_module
from django.conf import settings


def get_course_tab_view(*args, **kwargs):
    """ Get CourseTabView """
    backend_module = settings.NAU_FRAGMENTS_MODULE
    backend = import_module(backend_module)

    return backend.get_course_tab_view(*args, **kwargs)


def get_edx_fragment_view(*args, **kwargs):
    """ Get EdXFragmentView """
    backend_module = settings.NAU_FRAGMENTS_MODULE
    backend = import_module(backend_module)

    return backend.get_edx_fragment_view(*args, **kwargs)


def get_tab_fragment_view_mixin(*args, **kwargs):
    """ Get TabFragmentViewMixin """
    backend_module = settings.NAU_FRAGMENTS_MODULE
    backend = import_module(backend_module)

    return backend.get_tab_fragment_view_mixin(*args, **kwargs)


def get_enrolled_tab(*args, **kwargs):
    """
    Get EnrolledTab
    """
    backend_module = settings.NAU_FRAGMENTS_MODULE
    backend = import_module(backend_module)

    return backend.get_enrolled_tab(*args, **kwargs)
