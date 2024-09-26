""" CourseMetadata backend abstraction """

from importlib import import_module

from django.conf import settings


def get_cohort(*args, **kwargs):
    """
    Get the Course Cohort for the User that belongs the username if available other case return None.
    """
    backend_module = settings.NAU_COHORT_MODULE
    backend = import_module(backend_module)

    return backend.get_cohort(*args, **kwargs)

