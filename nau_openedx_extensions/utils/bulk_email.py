# -*- coding: utf-8 -*-
"""
Utilities for bulk email customization in NAU openedX extensions.
"""
from __future__ import absolute_import, unicode_literals

from django.conf import settings


def get_course_email_context_factory(prev_get_course_email_context_func):
    """
    Factory function to wrap the _get_course_email_context function.

    This allows us to inject custom organization data into the email context
    that is used for bulk email sending, while preserving the original functionality.

    Args:
        prev_get_course_email_context_func: The original _get_course_email_context function

    Returns:
        A wrapped version of the function with custom context injection
    """
    def get_course_email_context_wrapper(course):
        """
        Wraps the original get_course_email_context to add custom organization context.
        """
        # Call the original function to get the base email context
        email_context = prev_get_course_email_context_func(course)

        # Add custom NAU organization data to the context
        try:
            from opaque_keys.edx.keys import CourseKey  # pylint: disable=import-outside-toplevel # noqa
            from organizations.api import \
                get_course_organization  # pylint: disable=import-error,import-outside-toplevel # noqa

            course_id = str(course.id)
            course_key = CourseKey.from_string(course_id)
            organization = get_course_organization(course_key)

            if organization:
                email_context['organization_name'] = organization.get('name', None)
                organization_logo = organization.get('logo', None)
                if organization_logo:
                    logo_url = organization_logo.url
                    # Only prepend LMS_ROOT_URL if the URL is relative (not absolute)
                    if not logo_url.startswith(('http://', 'https://')):
                        logo_url = f'{settings.LMS_ROOT_URL}{logo_url}'
                    email_context['organization_logo'] = logo_url
        except Exception:  # pylint: disable=broad-except
            # If anything fails in getting organization data, just continue
            # with the base email context
            pass

        return email_context

    return get_course_email_context_wrapper
