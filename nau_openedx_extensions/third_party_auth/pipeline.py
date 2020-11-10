"""
Auth pipeline definitions.
"""
from django.conf import settings

from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel


def ensure_cartao_cidadao_data(strategy, details, user, uid, *args, **kwargs):  # pylint: disable=unused-argument
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
