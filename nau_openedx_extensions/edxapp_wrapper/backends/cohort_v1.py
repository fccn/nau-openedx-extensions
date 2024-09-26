"""
Cohort abstraction backend
"""
from common.djangoapps.student.models import get_user_by_username_or_email
from openedx.core.djangoapps.course_groups.cohorts import get_cohort as edxapp_get_cohort  # pylint: disable=import-error


def get_cohort(username, course_key):
    """
    Get the Course Cohort for the User that belongs the username if available other case return None.
    """
    user = get_user_by_username_or_email(username)
    return edxapp_get_cohort(user, course_key, assign=False, use_cached=False)
