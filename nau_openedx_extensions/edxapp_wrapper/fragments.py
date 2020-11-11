""" Fragments backend abstraction """
from __future__ import absolute_import, unicode_literals

from importlib import import_module

from django.conf import settings


def get_course_tab_view():
    """ Get CourseTabView """
    backend_module = settings.NAU_FRAGMENTS_MODULE
    backend = import_module(backend_module)

    return backend.get_course_tab_view()


def get_edx_fragment_view():
    """ Get EdXFragmentView """
    backend_module = settings.NAU_FRAGMENTS_MODULE
    backend = import_module(backend_module)

    return backend.get_edx_fragment_view()


def get_tab_fragment_view_mixin():
    """ Get TabFragmentViewMixin """
    backend_module = settings.NAU_FRAGMENTS_MODULE
    backend = import_module(backend_module)

    return backend.get_tab_fragment_view_mixin()


def get_enrolled_tab():
    """
    Get EnrolledTab
    """
    backend_module = settings.NAU_FRAGMENTS_MODULE
    backend = import_module(backend_module)

    return backend.get_enrolled_tab()
