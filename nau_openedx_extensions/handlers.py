from django.dispatch import receiver
from xmodule.modulestore.django import SignalHandler
import hashlib
import hmac
import json

from django.conf import settings

#from microsite_configuration import microsite
import requests
from xmodule.modulestore.django import modulestore

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

import logging
log = logging.getLogger(__name__)


class RichieSynchronizationError(Exception):
    """
    Error occurred while updating richie marketing site with an updated course run information.
    """
    pass

def update_course(course_key, *args, **kwargs):
    """Synchronize an OpenEdX course, identified by its course key, with a Richie instance."""
    course = modulestore().get_course(course_key)
    #edxapp_domain = microsite.get_value("site_domain", settings.LMS_BASE)
    edxapp_domain = configuration_helpers.get_value('site_domain', settings.LMS_BASE)

    data = {
        "resource_link": "https://{:s}/courses/{!s}/info".format(
            edxapp_domain, course_key
        ),
        "start": course.start and course.start.isoformat(),
        "end": course.end and course.end.isoformat(),
        "enrollment_start": course.enrollment_start and course.enrollment_start.isoformat(),
        "enrollment_end": course.enrollment_end and course.enrollment_end.isoformat(),
        "languages": [course.language or settings.LANGUAGE_CODE],
    }

    richie_course_hook = configuration_helpers.get_value(
        'RICHIE_COURSE_HOOK',
        settings.RICHIE_COURSE_HOOK
    )
    if richie_course_hook:
        signature = hmac.new(
            richie_course_hook["secret"].encode("utf-8"),
            msg=json.dumps(data).encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        richie_url = richie_course_hook.get("url")
        timeout = richie_course_hook.get("timeout", "5")
        
        try:
            response = requests.post(
                richie_url,
                json=data,
                headers={"Authorization": "SIG-HMAC-SHA256 {:s}".format(signature)},
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            status_code = response.status_code
            msg = (
                f"Error synchronizing course {course_key} to richie site {richie_url} "
                f"it returned the HTTP status code {status_code}"
            )
            log.error(msg)
            raise RichieSynchronizationError(msg)
        except requests.exceptions.RequestException as e:
            msg = (
                f"Error synchronizing course {course_key} to richie site {richie_url}"
            )
            log.error(msg)
            raise RichieSynchronizationError(msg)


@receiver(SignalHandler.course_published, dispatch_uid='update_course_on_publish')
def update_course_on_publish(sender, course_key, **kwargs):
    update_course(course_key)

