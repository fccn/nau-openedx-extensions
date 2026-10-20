"""
Helpers to get the canonical casing of course keys.
"""

import hashlib
import logging
import re

from django.core.cache import cache
from django.db import DatabaseError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey

from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview

log = logging.getLogger(__name__)

CACHE_PREFIX = "nau_openedx_extensions.canonical_course_key."
FOUND_CACHE_TIMEOUT = 60 * 60
NOT_FOUND_CACHE_TIMEOUT = 60
KEYS_IN_PATH_REGEX = re.compile(r"(?:course|block)-v1:[^/\s]+")
# Real URLs have at most a course key and a couple of block keys. Limiting how many are replaced
# bounds the database lookups that a single (possibly anonymous) request can trigger.
MAX_KEYS_IN_PATH = 3


def get_canonical_course_key(course_key: CourseKey) -> CourseKey:
    """
    Return the course key with the casing stored in the course overview.

    Returns the given key when there is no course overview for it, so it is always safe to use.
    The branch and version of the given key, if any, are kept.
    """
    lookup_key = str(course_key.for_branch(None).version_agnostic())
    cache_key = CACHE_PREFIX + hashlib.sha256(lookup_key.lower().encode("utf-8")).hexdigest()

    canonical = cache.get(cache_key)
    if canonical is None:
        try:
            canonical_key = CourseOverview.objects.filter(id__iexact=lookup_key).values_list("id", flat=True).first()
        except DatabaseError as error:
            # Not an exception log: during a database outage this is logged for every key of every request.
            log.warning("Unable to get the canonical course key of %r: %s", lookup_key, error)
            return course_key
        canonical = str(canonical_key) if canonical_key else ""
        cache.set(cache_key, canonical, FOUND_CACHE_TIMEOUT if canonical else NOT_FOUND_CACHE_TIMEOUT)

    if not canonical or canonical == lookup_key:
        return course_key
    return CourseKey.from_string(canonical).for_branch(course_key.branch).for_version(course_key.version_guid)


def canonicalize_course_keys_in_path(path: str) -> str:
    """
    Return the URL path with the casing of its course and block keys replaced by the canonical one.

    Anything that is not a known course key is kept unchanged, and so are the keys after the first
    `MAX_KEYS_IN_PATH`.
    """

    def replace_key(match: re.Match) -> str:
        key_string = match.group(0)
        try:
            if key_string.startswith("block-v1:"):
                usage_key = UsageKey.from_string(key_string)
                course_key = get_canonical_course_key(usage_key.course_key)
                return str(usage_key.map_into_course(course_key))
            return str(get_canonical_course_key(CourseKey.from_string(key_string)))
        except InvalidKeyError:
            return key_string

    return KEYS_IN_PATH_REGEX.sub(replace_key, path, count=MAX_KEYS_IN_PATH)
