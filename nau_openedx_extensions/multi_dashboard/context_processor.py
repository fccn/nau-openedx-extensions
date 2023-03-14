from common.djangoapps.student.views.dashboard import get_course_enrollments
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


def get_multi_dashboard_context(existing_context, *args, **kwargs):
    """
    Processor to get additional course enrollments for the same user but out of the current site.
    The site must contain a list of orgs that will be shown under the key: `other_sites_orgs`.

    See: https://github.com/openedx/edx-django-utils/tree/master/edx_django_utils/plugins/docs/decisions/0001-plugin-contexts.rst#plugin-contexts
    Returns:
        dictionary of lists: dictionary with one enrollments
            dict["other_sites_enrollments"] = list of enrollment objects.
            dict["lms_root_urls"] = dict with course_ids as keys and the LMS_ROOT of the site,
                                    who's orgs_site_filter matches the course's .org.
    """
    additional_context = {}
    user = existing_context["user"]

    org_blacklist = configuration_helpers.get_current_site_orgs()
    org_whitelist = configuration_helpers.get_value('other_sites_orgs', [])

    other_sites_enrollments = list(get_course_enrollments(user, org_whitelist, org_blacklist))

    additional_context['other_sites_enrollments'] = other_sites_enrollments

    lms_root_urls = {}
    for index, enrollment in enumerate(other_sites_enrollments):
        lms_root_urls[enrollment.course_id] = configuration_helpers.get_value_for_org(
            "enrollment.course.org", "LMS_ROOT"
        )

    additional_context['lms_root_urls'] = lms_root_urls

    return additional_context
