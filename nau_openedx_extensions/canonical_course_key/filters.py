"""
Open edX filter pipeline steps that use the canonical casing of course keys.
"""

from typing import Any, Union

from django.conf import settings
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx_filters import PipelineStep

from nau_openedx_extensions.canonical_course_key.utils import get_canonical_course_key


class CourseHomeUrlCanonicalCourseKey(PipelineStep):  # pylint: disable=too-few-public-methods
    """
    Make the course home URL use the canonical casing of the course key.
    """

    def run_filter(  # pylint: disable=arguments-differ
        self, course_key: Union[CourseKey, str], course_home_url: str
    ) -> dict[str, Any]:
        """
        Return the canonical course key and the course home URL built with it.
        """
        if not getattr(settings, "NAU_CANONICAL_COURSE_KEYS_ENABLED", True):
            return {}
        try:
            key = CourseKey.from_string(course_key) if isinstance(course_key, str) else course_key
        except InvalidKeyError:
            return {}

        canonical_key = get_canonical_course_key(key)
        if canonical_key == key:
            return {}
        return {
            "course_key": canonical_key,
            "course_home_url": course_home_url.replace(str(key), str(canonical_key)),
        }
