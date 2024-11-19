"""
Cohort abstraction backend
"""
import logging
import traceback

from django.contrib.auth.models import User  # lint-amnesty, pylint: disable=imported-auth-user
from django.db.models import Q
from openedx.core.djangoapps.course_groups.cohorts import \
    get_cohort as edxapp_get_cohort  # pylint: disable=import-error

log = logging.getLogger(__name__)


def get_cohort(username, course_key):
    """
    Get the Course Cohort for the User that belongs the username if available other case return None.
    """
    user = None
    # pylint: disable=broad-except
    try:
        user = User.objects.get(Q(username=username))
    except Exception as e:
        log.error("On get_cohort method error getting user %s, error: %s, stacktrace: %s", username, str(e), traceback.format_exc())
    # pylint: disable=broad-except
    try:
        return edxapp_get_cohort(user, course_key, assign=False, use_cached=False)
    except Exception as e:
        log.error("On get_cohort method error getting cohort course_key: %s, error: %s, stacktrace: %s", course_key, str(e), traceback.format_exc())
        return None
