"""
This file defines overrides of the context render of course certificates using an Open edX Filters pipeline step.
"""
import logging

from openedx_filters import PipelineStep

from nau_openedx_extensions.edxapp_wrapper.cohort import get_cohort

log = logging.getLogger(__name__)

class CertificatesContextCohortOverride(PipelineStep):
    """
    Override the certificates render template context with information from the student cohort.
    If user has a cohort and that cohort has custom certificate overrides, then override the root context variables
    with the cohorted ones.

    Example usage:
    Add the following configurations to your configuration file:
        "OPEN_EDX_FILTERS_CONFIG": {
            "org.openedx.learning.certificate.render.started.v1": {
                "fail_silently": false,
                "pipeline": [
                    "nau_openedx_extensions.certificates.context_overrides.CertificatesContextCohortOverride"
                ]
            }
        }

    Configure course on field "Certificate Web/HTML View Overrides" with:
        {
            "footer_additional_logo": "https://lms.example.com/some_logo.png",
            "cohort_overrides": {
                "test": {
                    "footer_additional_logo": "https://lms.example.com/override_logo.png"
                }
            }
        }
    """

    def run_filter(self, context, custom_template):  # pylint: disable=unused-argument, arguments-differ
        """
        The filter logic.
        """
        username = context['username']
        course_key = context['course_id']
        if 'cohort_overrides' in context:
            cohort = get_cohort(username, course_key)
            if cohort:
                if cohort.name in context['cohort_overrides']:
                    cohort_override_dict = context['cohort_overrides'][cohort.name]
                    context.update(cohort_override_dict)
                else:
                    log.info("The user '%s' enrollment on course '%s' doesn't have a cohort certificate context overrides configured for the cohort '%s'.", username, course_key, cohort.name)
            else:
                log.info("User '%s' not in a cohort on course '%s'", username, course_key)
        else:
            log.info("No Certificates context cohort_overrides defined on course '%s'", course_key)

        return {"context": context, "custom_template": custom_template}
