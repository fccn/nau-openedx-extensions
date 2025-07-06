"""
Content backend abstraction.
"""

from importlib import import_module

from django.conf import settings


def get_course_overview_model():
    """
    Wrapper for `openedx.core.djangoapps.content.course_overviews.models.CourseOverview` in edx-platform.
    """
    backend_function = settings.NAU_CONTENT_MODULE
    backend = import_module(backend_function)
    return backend.CourseOverview


CourseOverview = get_course_overview_model()
