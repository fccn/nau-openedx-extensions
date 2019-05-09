from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

# Backwards compatible settings.AUTH_USER_MODEL
USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class NauUserExtendedModel(models.Model):
    """
    Holds data autorization field
    Used during user registration as a form extension.
    """
    user = models.OneToOneField(USER_MODEL, null=True)
    data_authorization = models.BooleanField(
        verbose_name=_("I authorize data processing for this site "),
        default=False
    )
    citizen_card = models.CharField(
        verbose_name=_("Citizen Card"),
        max_length=16,
        blank=True,
        null=True
    )
    nif = models.CharField(
        verbose_name=_("NIF"),
        max_length=9,
        blank=True,
        null=True
    )
