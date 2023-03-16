"""
Shared multi organization LMS dashboard. It allows to adds an other sites enrollment section in
the dashboard, so the user can find other courses that he is already enrolled more easy.
"""

from common.djangoapps.student.views.dashboard import get_course_enrollments  # pylint: disable=import-error
from common.djangoapps.student.views.dashboard import get_dashboard_course_limit  # pylint: disable=import-error
from django.conf import settings
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers  # pylint: disable=import-error
from organizations.api import get_organizations  # pylint: disable=import-error


def get_multi_dashboard_context(existing_context, *args, **kwargs):
    """
    Processor to get additional course enrollments for the same user but out of the current site.
    The site must contain a list of orgs that will be shown under the key: `other_sites_orgs`.

    See: https://github.com/openedx/edx-django-utils/tree/master/edx_django_utils/plugins/docs/decisions/0001-plugin-contexts.rst#plugin-contexts
    Returns:
        dictionary of lists: dictionary with one enrollments
            dict["other_sites_enrollments"] = list of enrollment objects.
            dict["lms_root_urls"] = dict with course_ids as keys and the LMS_ROOT_URL of the site,
                                    who's orgs_site_filter matches the course's .org.
    """  # noqa
    additional_context = {}
    user = existing_context["user"]

    current_site_orgs = configuration_helpers.get_current_site_orgs()
    orgs_with_site = configuration_helpers.get_all_orgs()
    all_orgs = [(org["short_name"]) for org in get_organizations()]

    if current_site_orgs:
        org_whitelist = all_orgs
        org_blacklist = current_site_orgs
    else:
        # primary site show by default all courses from all orgs without a site
        # so we show all courses from orgs with site and black list all courses
        # from orgs without a site.
        org_whitelist = orgs_with_site
        orgs_without_site = []
        for org in all_orgs:
            if org not in orgs_with_site:
                orgs_without_site.append(org)
        org_blacklist = orgs_without_site

    other_sites_enrollments = list(get_course_enrollments(
        user, org_whitelist, org_blacklist, get_dashboard_course_limit()))

    additional_context['other_sites_enrollments'] = other_sites_enrollments

    lms_root_urls = {}
    for enrollment in other_sites_enrollments:
        lms_root_urls[enrollment.course_id] = configuration_helpers.get_value_for_org(
            enrollment.course.org, "LMS_ROOT_URL", settings.LMS_ROOT_URL
        )

    additional_context['lms_root_urls'] = lms_root_urls

    return additional_context
