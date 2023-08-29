"""
Auth pipeline definitions.
"""
from __future__ import absolute_import, unicode_literals

import logging

from django.conf import settings

from edx_django_utils.user import (
    generate_password,
)  # pylint: disable=import-error,unused-import

from common.djangoapps.student.models import (
    UserAttribute,
)  # pylint: disable=import-error,no-name-in-module

from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel

log = logging.getLogger(__name__)


def ensure_cartao_cidadao_data(strategy, details, user, uid, *args, **kwargs):
    """
    The part of the pipeline that stores the information from the portuguese authentication service.
    """
    if not user:
        return

    if not uid.startswith(settings.NAU_CC_ALLOWED_SLUG):
        return

    changed = False
    protected = ("username", "id", "pk", "email") + tuple(
        strategy.setting("PROTECTED_USER_FIELDS", [])
    )

    # Make sure the user has a nau extended model.
    if not hasattr(user, "nauuserextendedmodel"):
        NauUserExtendedModel.objects.create(user=user)

    # Update the NAU extended model.
    for name, value in details.items():
        if (
            value is None
            or not hasattr(user.nauuserextendedmodel, name)
            or name in protected
        ):
            continue

        current_value = getattr(user.nauuserextendedmodel, name, None)
        if current_value == value:
            continue

        changed = True
        setattr(user.nauuserextendedmodel, name, value)

    if changed:
        user.nauuserextendedmodel.save()


# pylint: disable=unused-argument,keyword-arg-before-vararg
def ensure_new_user_has_usable_password(backend, user=None, **kwargs):
    """
    This pipeline function assigns an usable password to an user in case that
    the user has an unusable password on user creation. At the creation of new users
    through some TPA providers, some of them are created with an unusable password,
    a user with an unusable password cannot login properly in the platform if
    the common.djangoapps.third_party.pipeline.set_logged_in_cookies step is enabled.

    It should run after `social_core.pipeline.user.create_user` on the SOCIAL_AUTH_TPA_SAML_PIPELINE.
    """

    is_new = kwargs.get("is_new")

    if user and is_new and not user.has_usable_password():
        user.set_password(generate_password(length=25))
        user.save()

        UserAttribute.set_user_attribute(user, "auto_password_via_tpa_pipeline", "true")

        log.info("Assign a usable password to the user %s on creation", user.username)
