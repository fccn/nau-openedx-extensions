"""
Context extender module for edx-platform certificates
"""
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import ugettext as _

from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel
from nau_openedx_extensions.edxapp_wrapper.grades import get_course_grades
from nau_openedx_extensions.edxapp_wrapper.registration import get_registration_extension_form


def update_cert_context(*args, **kwargs):
    """
    Updates certifcates context with custom data for the user within
    the course context
    """
    updated_fields = {}
    context = kwargs['context']
    user = kwargs['user']
    course = kwargs['course']
    nau_cert_settings = course.cert_html_view_overrides.get('nau_certs_settings')

    update_context_with_custom_form(user, NauUserExtendedModel, context, updated_fields)
    if nau_cert_settings:
        update_context_with_grades(user, course, context, nau_cert_settings, updated_fields)
        update_context_with_interpolated_strings(course, context, nau_cert_settings, updated_fields)


def update_context_with_custom_form(user, custom_model, context, updated_fields):
    """
    Updates the context in-place with extra user information
    """
    custom_form = get_registration_extension_form()
    try:
        custom_model_instance = custom_model.objects.get(user=user)
    except ObjectDoesNotExist:
        # If a custom model does not exist for the user, just return
        return

    for field in custom_form.fields.keys():
        context_element = {
            field: getattr(custom_model_instance, field, "")
        }
        context.update(context_element)
        updated_fields.update(context_element)


def update_context_with_grades(user, course, context, settings, updated_fields):
    """
    Updates certifcates context with grades data for the user
    """
    if settings.get('update_with_grades_context', False):
        try:
            grades = get_course_grades(user, course)
            context_element = {
                "course_letter_grade": grades.letter_grade or '',
                "user_has_approved_course": grades.passed,
                "course_percent_grade": grades.percent,
            }
        except Exception:
            pass
        else:
            context.update(context_element)
            updated_fields.update(context_element)


def update_context_with_interpolated_strings(course, context, settings, updated_fields):
    """
    Updates certificate context using custom interpolated strings.
    Applies the corresponding translation before updating the context.
    """
    interpolated_strings = get_interpolated_strings(settings)

    if interpolated_strings:
        for key, value in interpolated_strings.iteritems():
            try:
                formatted_string = value.format(**updated_fields)
            except (ValueError, AttributeError, KeyError):
                continue
            else:
                context.update({
                    key: _(formatted_string)
                })


def get_interpolated_strings(settings):
    """
    Returns a dict with custom interpolated strings.
    Returns None if the corresponding key is not defined
    """

    return settings.get('interpolated_strings')
