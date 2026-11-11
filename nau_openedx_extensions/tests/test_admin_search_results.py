"""
Tests for the database that the search results of the admin screens come from.

The search is read from the replica when the request only reads. A request that can write keeps the writer, because
the admin actions of the change list, ``delete_selected`` among them, write through the queryset of the search.
"""
from unittest.mock import patch

from common.djangoapps.student.models import CourseEnrollment
from django.conf import settings
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from nau_openedx_extensions.custom_registration_form.admin import NauUserExtendedModelAdmin
from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel
from nau_openedx_extensions.partner_integration.admin import SSOPartnerIntegrationAdmin
from nau_openedx_extensions.partner_integration.models import SSOPartnerIntegration
from nau_openedx_extensions.student.admin import NAUCourseEnrollmentAdmin


class SearchResultsDatabaseMixin:
    """
    Tests shared by the admin classes that search through the replica.

    The test case defines the ``admin_class`` and its ``model``. The ``read_replica`` alias exists, as in the NAU
    deployments, and a queryset only has to be pinned to it: nothing opens a connection.
    """

    def setUp(self):
        super().setUp()
        replica = patch.dict(settings.DATABASES, {"read_replica": settings.DATABASES["default"]})
        replica.start()
        self.addCleanup(replica.stop)
        self.model_admin = self.admin_class(self.model, AdminSite())

    def search(self, method):
        """
        Return the queryset of the search of a change list page requested with the HTTP ``method``.
        """
        request = RequestFactory().generic(method, "/admin/?q=abcd")
        queryset, _use_distinct = self.model_admin.get_search_results(request, self.model.objects.all(), "abcd")
        return queryset

    def test_a_search_that_only_reads_is_pinned_to_the_replica(self):
        for method in ("GET", "HEAD"):
            with self.subTest(method=method):
                self.assertEqual(self.search(method).db, "read_replica")

    def test_a_search_that_can_write_stays_on_the_writer(self):
        """The bulk action submitted with the page, ``delete_selected`` for one, deletes through this queryset."""
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self.search(method).db, "default")


class NauUserExtendedModelAdminSearchResultsTests(SearchResultsDatabaseMixin, TestCase):
    """Search results of the NauUserExtendedModel admin."""
    admin_class = NauUserExtendedModelAdmin
    model = NauUserExtendedModel


class NAUCourseEnrollmentAdminSearchResultsTests(SearchResultsDatabaseMixin, TestCase):
    """Search results of the CourseEnrollment admin."""
    admin_class = NAUCourseEnrollmentAdmin
    model = CourseEnrollment


class SSOPartnerIntegrationAdminSearchResultsTests(SearchResultsDatabaseMixin, TestCase):
    """Search results of the SSOPartnerIntegration admin."""
    admin_class = SSOPartnerIntegrationAdmin
    model = SSOPartnerIntegration
