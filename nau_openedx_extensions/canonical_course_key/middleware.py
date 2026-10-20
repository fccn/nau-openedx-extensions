"""
Middleware that makes the platform handle requests using the canonical casing of course keys.
"""

import logging
from typing import Callable

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpRequest, HttpResponse

from nau_openedx_extensions.canonical_course_key.utils import canonicalize_course_keys_in_path

log = logging.getLogger(__name__)


class CanonicalCourseKeyMiddleware:  # pylint: disable=too-few-public-methods
    """
    Replace the course and block keys of the request path by the ones with the canonical casing.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        if not getattr(settings, "NAU_CANONICAL_COURSE_KEYS_ENABLED", True):
            raise MiddlewareNotUsed()
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path_info = request.path_info
        if "course-v1:" in path_info or "block-v1:" in path_info:
            try:
                canonical_path_info = canonicalize_course_keys_in_path(path_info)
            except Exception:  # pylint: disable=broad-except
                # This is a best-effort normalization, it must never break the request.
                # The path is user controlled, so it is logged escaped.
                log.exception("Unable to use the canonical course key in %r", path_info)
                canonical_path_info = path_info
            if canonical_path_info != path_info:
                request.path = request.path[: len(request.path) - len(path_info)] + canonical_path_info
                request.path_info = canonical_path_info
                request.META["PATH_INFO"] = canonical_path_info
        return self.get_response(request)
