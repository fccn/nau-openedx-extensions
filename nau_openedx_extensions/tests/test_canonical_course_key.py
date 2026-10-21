"""
Tests for the canonical casing of course keys.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import MiddlewareNotUsed
from django.db import DatabaseError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import override_settings
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangoapps.content.course_overviews.tests.factories import (  # pylint: disable=import-error
    CourseOverviewFactory,
)

from nau_openedx_extensions.canonical_course_key import middleware, utils
from nau_openedx_extensions.canonical_course_key.filters import CourseHomeUrlCanonicalCourseKey
from nau_openedx_extensions.canonical_course_key.middleware import CanonicalCourseKeyMiddleware
from nau_openedx_extensions.canonical_course_key.utils import (
    FOUND_CACHE_TIMEOUT,
    MAX_KEYS_IN_PATH,
    NOT_FOUND_CACHE_TIMEOUT,
    canonicalize_course_keys_in_path,
    get_canonical_course_key,
)
from nau_openedx_extensions.settings.common import _append_filter_pipeline_step

CANONICAL_COURSE = "course-v1:Org+IBPC+2025_T1"
WRONG_CASE_COURSE = "course-v1:Org+iBPC+2025_T1"
CANONICAL_BLOCK = "block-v1:Org+IBPC+2025_T1+type@sequential+block@abc123"
WRONG_CASE_BLOCK = "block-v1:Org+iBPC+2025_T1+type@sequential+block@abc123"
UNKNOWN_COURSE = "course-v1:Org+Unknown+Run"
VERSION = "5f1c2d3e4a5b6c7d8e9f0a1b"
LOCMEM_CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


class CanonicalCourseKeyTestCase(TestCase):
    """
    Base class that creates the course overview with the canonical casing.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        # LocMemCache keeps its data between tests, so clear it while the cache settings are still overridden.
        self.addCleanup(cache.clear)
        CourseOverviewFactory(id=CourseKey.from_string(CANONICAL_COURSE))


class GetCanonicalCourseKeyTest(CanonicalCourseKeyTestCase):
    """
    Test getting the course key with the casing stored in the course overview.
    """

    def test_wrong_casing_returns_canonical_key(self):
        """A key with a different casing is replaced by the stored one."""
        canonical = get_canonical_course_key(CourseKey.from_string(WRONG_CASE_COURSE))

        self.assertEqual(str(canonical), CANONICAL_COURSE)
        self.assertIsInstance(canonical, CourseKey)

    def test_canonical_key_is_unchanged(self):
        """A key that already has the stored casing is returned as is."""
        course_key = CourseKey.from_string(CANONICAL_COURSE)

        self.assertIs(get_canonical_course_key(course_key), course_key)

    def test_unknown_course_is_unchanged(self):
        """A key without a course overview is returned as is."""
        course_key = CourseKey.from_string(UNKNOWN_COURSE)

        self.assertIs(get_canonical_course_key(course_key), course_key)

    def test_branch_and_version_are_kept(self):
        """The branch and the version of the key do not prevent the canonical casing, and are kept."""
        course_key = CourseKey.from_string(f"{WRONG_CASE_COURSE}+branch@draft-branch+version@{VERSION}")

        canonical = get_canonical_course_key(course_key)

        self.assertEqual(str(canonical), f"{CANONICAL_COURSE}+branch@draft-branch+version@{VERSION}")

    def test_database_error_returns_the_given_key(self):
        """The key is returned as is, and the error is logged, when the course overview cannot be read."""
        course_key = CourseKey.from_string(WRONG_CASE_COURSE)

        with patch.object(utils.CourseOverview.objects, "filter", side_effect=DatabaseError):
            with self.assertLogs(utils.log, "ERROR"):
                self.assertIs(get_canonical_course_key(course_key), course_key)

    def test_cache_timeouts(self):
        """Known courses are cached for longer than unknown ones."""
        fake_cache = MagicMock()
        fake_cache.get.return_value = None

        with patch.object(utils, "cache", fake_cache):
            get_canonical_course_key(CourseKey.from_string(WRONG_CASE_COURSE))
            get_canonical_course_key(CourseKey.from_string(UNKNOWN_COURSE))

        stored = [(call.args[1], call.args[2]) for call in fake_cache.set.call_args_list]
        self.assertEqual(stored, [(CANONICAL_COURSE, FOUND_CACHE_TIMEOUT), ("", NOT_FOUND_CACHE_TIMEOUT)])


@override_settings(CACHES=LOCMEM_CACHES)
class CanonicalCourseKeyCacheTest(CanonicalCourseKeyTestCase):
    """
    Test the cache of the canonical keys, the tests settings use a cache that stores nothing.
    """

    def test_result_is_cached(self):
        """The database is only queried the first time."""
        wrong_case_key = CourseKey.from_string(WRONG_CASE_COURSE)
        get_canonical_course_key(wrong_case_key)

        with self.assertNumQueries(0):
            canonical = get_canonical_course_key(wrong_case_key)

        self.assertEqual(str(canonical), CANONICAL_COURSE)

    def test_unknown_course_is_cached(self):
        """The database is only queried the first time for the courses without course overview too."""
        course_key = CourseKey.from_string(UNKNOWN_COURSE)
        get_canonical_course_key(course_key)

        with self.assertNumQueries(0):
            canonical = get_canonical_course_key(course_key)

        self.assertIs(canonical, course_key)


class CanonicalizeCourseKeysInPathTest(CanonicalCourseKeyTestCase):
    """
    Test replacing the course and block keys of a URL path.
    """

    def test_course_key_in_api_path(self):
        """A course key at the end of the path is replaced."""
        path = canonicalize_course_keys_in_path(f"/api/courseware/course/{WRONG_CASE_COURSE}")

        self.assertEqual(path, f"/api/courseware/course/{CANONICAL_COURSE}")

    def test_course_key_between_slashes(self):
        """A course key in the middle of the path is replaced."""
        path = canonicalize_course_keys_in_path(f"/courses/{WRONG_CASE_COURSE}/course/")

        self.assertEqual(path, f"/courses/{CANONICAL_COURSE}/course/")

    def test_course_and_block_keys(self):
        """The course part of block keys is replaced too, keeping the rest of the key."""
        path = canonicalize_course_keys_in_path(f"/courses/{WRONG_CASE_COURSE}/jump_to/{WRONG_CASE_BLOCK}")

        self.assertEqual(path, f"/courses/{CANONICAL_COURSE}/jump_to/{CANONICAL_BLOCK}")
        self.assertIsInstance(UsageKey.from_string(CANONICAL_BLOCK), UsageKey)

    def test_block_key_with_branch_and_version(self):
        """The course part of block keys with a branch and a version is replaced too."""
        block_suffix = "+type@sequential+block@abc123"
        wrong_case_block = f"block-v1:Org+iBPC+2025_T1+branch@draft-branch+version@{VERSION}{block_suffix}"
        canonical_block = f"block-v1:Org+IBPC+2025_T1+branch@draft-branch+version@{VERSION}{block_suffix}"

        path = canonicalize_course_keys_in_path(f"/xblock/{wrong_case_block}")

        self.assertEqual(path, f"/xblock/{canonical_block}")

    def test_other_paths_are_unchanged(self):
        """Paths without course keys, with unknown courses, or with invalid keys are kept."""
        for path in (
            "/dashboard",
            f"/api/courseware/course/{UNKNOWN_COURSE}",
            "/api/courseware/course/course-v1:invalid",
            "/xblock/block-v1:Org+Unknown+Run+type@sequential+block@abc123",
            "/xblock/block-v1:invalid",
        ):
            self.assertEqual(canonicalize_course_keys_in_path(path), path)

    def test_number_of_lookups_is_limited(self):
        """A path with many keys does not make a query for each one of them."""
        path = "/" + "/".join(f"course-v1:Org+Unknown{number}+Run" for number in range(20))

        with self.assertNumQueries(MAX_KEYS_IN_PATH):
            self.assertEqual(canonicalize_course_keys_in_path(path), path)

    def test_keys_after_the_limit_are_unchanged(self):
        """Only the first keys of the path are replaced."""
        unknown_keys = "/".join(f"course-v1:Org+Unknown{number}+Run" for number in range(MAX_KEYS_IN_PATH))
        path = f"/{unknown_keys}/{WRONG_CASE_COURSE}"

        self.assertEqual(canonicalize_course_keys_in_path(path), path)


class CanonicalCourseKeyMiddlewareTest(CanonicalCourseKeyTestCase):
    """
    Test the middleware that uses the canonical casing of the course keys in the requests.
    """

    def get_handled_request(self, path):
        """Return the request as seen by the view."""
        handled = {}

        def get_response(request):
            handled["request"] = request
            return HttpResponse()

        CanonicalCourseKeyMiddleware(get_response)(RequestFactory().get(path))
        return handled["request"]

    def test_wrong_casing_in_path_is_replaced(self):
        """The view sees the path with the canonical course key."""
        request = self.get_handled_request(f"/api/courseware/course/{WRONG_CASE_COURSE}?a=b")

        self.assertEqual(request.path_info, f"/api/courseware/course/{CANONICAL_COURSE}")
        self.assertEqual(request.path, f"/api/courseware/course/{CANONICAL_COURSE}")
        self.assertEqual(request.META["PATH_INFO"], f"/api/courseware/course/{CANONICAL_COURSE}")
        self.assertEqual(request.GET["a"], "b")

    def test_canonical_path_is_unchanged(self):
        """Requests that already use the canonical key are not modified."""
        path = f"/api/courseware/course/{CANONICAL_COURSE}"

        self.assertEqual(self.get_handled_request(path).path_info, path)

    def test_path_without_course_key_makes_no_queries(self):
        """The database is not used for the other requests."""
        with self.assertNumQueries(0):
            self.get_handled_request("/dashboard")

    @override_settings(NAU_CANONICAL_COURSE_KEYS_ENABLED=False)
    def test_disabled(self):
        """The middleware is not used when disabled."""
        with self.assertRaises(MiddlewareNotUsed):
            CanonicalCourseKeyMiddleware(lambda request: HttpResponse())

    def test_errors_do_not_break_the_request(self):
        """The request is handled as is when the canonical key cannot be obtained."""
        path = f"/api/courseware/course/{WRONG_CASE_COURSE}"

        with patch.object(middleware, "canonicalize_course_keys_in_path", side_effect=ConnectionError):
            with self.assertLogs(middleware.log, "ERROR"):
                self.assertEqual(self.get_handled_request(path).path_info, path)

    def test_path_is_logged_escaped(self):
        """The path is user controlled, so control characters in it cannot forge log lines."""
        path = f"/api/courseware/course/{WRONG_CASE_COURSE}%0AERROR%20forged"

        with patch.object(middleware, "canonicalize_course_keys_in_path", side_effect=ConnectionError):
            with self.assertLogs(middleware.log, "ERROR") as logs:
                self.get_handled_request(path)

        message = logs.records[0].getMessage()
        self.assertNotIn("\n", message)
        self.assertIn("\\nERROR forged", message)


class CourseHomeUrlCanonicalCourseKeyTest(CanonicalCourseKeyTestCase):
    """
    Test the filter step that uses the canonical course key in the course home URL.
    """

    HOME_URL_TEMPLATE = "https://apps.example.com/learning/course/{}/home"

    def run_step(self, course_key):
        """Run the filter step for the course key."""
        return CourseHomeUrlCanonicalCourseKey("filter_type", []).run_filter(
            course_key=course_key,
            course_home_url=self.HOME_URL_TEMPLATE.format(course_key),
        )

    def test_wrong_casing_returns_canonical_url(self):
        """The URL is built with the canonical course key."""
        result = self.run_step(CourseKey.from_string(WRONG_CASE_COURSE))

        self.assertEqual(str(result["course_key"]), CANONICAL_COURSE)
        self.assertEqual(result["course_home_url"], self.HOME_URL_TEMPLATE.format(CANONICAL_COURSE))

    def test_course_key_as_string(self):
        """A course key given as a string is supported."""
        result = self.run_step(WRONG_CASE_COURSE)

        self.assertEqual(result["course_home_url"], self.HOME_URL_TEMPLATE.format(CANONICAL_COURSE))

    def test_canonical_key_is_unchanged(self):
        """Nothing is returned when the course key already has the canonical casing."""
        self.assertEqual(self.run_step(CourseKey.from_string(CANONICAL_COURSE)), {})

    def test_invalid_key_is_unchanged(self):
        """Nothing is returned for an invalid course key."""
        self.assertEqual(self.run_step("not-a-course-key"), {})

    @override_settings(NAU_CANONICAL_COURSE_KEYS_ENABLED=False)
    def test_disabled(self):
        """Nothing is returned when disabled."""
        self.assertEqual(self.run_step(CourseKey.from_string(WRONG_CASE_COURSE)), {})


class CanonicalCourseKeySettingsTest(TestCase):
    """
    Test that the plugin registers the middleware and the filter step.
    """

    FILTER_TYPE = "org.openedx.learning.course.homepage.url.creation.started.v1"
    FILTER_STEP = "nau_openedx_extensions.canonical_course_key.filters.CourseHomeUrlCanonicalCourseKey"
    MIDDLEWARE = "nau_openedx_extensions.canonical_course_key.middleware.CanonicalCourseKeyMiddleware"

    def test_registered_once(self):
        """The middleware and the filter step are configured, and only once."""
        self.assertEqual(settings.MIDDLEWARE.count(self.MIDDLEWARE), 1)
        self.assertEqual(settings.OPEN_EDX_FILTERS_CONFIG[self.FILTER_TYPE]["pipeline"].count(self.FILTER_STEP), 1)


class AppendFilterPipelineStepTest(SimpleTestCase):
    """
    Test adding a step to the configuration of an Open edX filter.
    """

    FILTER_TYPE = "org.example.filter.v1"
    OTHER_FILTER_TYPE = "org.example.other.v1"

    def test_creates_the_configuration(self):
        """The filters configuration is created when there is none."""
        fake_settings = SimpleNamespace()

        _append_filter_pipeline_step(fake_settings, self.FILTER_TYPE, "module.Step")

        self.assertEqual(
            fake_settings.OPEN_EDX_FILTERS_CONFIG,
            {self.FILTER_TYPE: {"fail_silently": True, "pipeline": ["module.Step"]}},
        )

    def test_keeps_the_existing_configuration(self):
        """The steps and the options of the filters that are already configured are kept."""
        fake_settings = SimpleNamespace(
            OPEN_EDX_FILTERS_CONFIG={
                self.FILTER_TYPE: {"fail_silently": False, "pipeline": ["module.OtherStep"]},
                self.OTHER_FILTER_TYPE: {"fail_silently": True, "pipeline": ["module.UnrelatedStep"]},
            }
        )

        _append_filter_pipeline_step(fake_settings, self.FILTER_TYPE, "module.Step")

        self.assertEqual(
            fake_settings.OPEN_EDX_FILTERS_CONFIG,
            {
                self.FILTER_TYPE: {"fail_silently": False, "pipeline": ["module.OtherStep", "module.Step"]},
                self.OTHER_FILTER_TYPE: {"fail_silently": True, "pipeline": ["module.UnrelatedStep"]},
            },
        )

    def test_step_is_not_added_twice(self):
        """Adding the same step again does not repeat it."""
        fake_settings = SimpleNamespace()

        _append_filter_pipeline_step(fake_settings, self.FILTER_TYPE, "module.Step")
        _append_filter_pipeline_step(fake_settings, self.FILTER_TYPE, "module.Step")

        self.assertEqual(fake_settings.OPEN_EDX_FILTERS_CONFIG[self.FILTER_TYPE]["pipeline"], ["module.Step"])
