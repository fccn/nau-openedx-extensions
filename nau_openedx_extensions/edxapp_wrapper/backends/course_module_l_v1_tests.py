""" Course block backend abstraction for tests"""

from unittest.mock import Mock


def get_other_course_settings(course_id):   # pylint: disable=unused-argument
    """Get Other Course Settings Mock."""
    return Mock()
