"""
Models for Nau extended user
"""

from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.contrib.auth.models import User  # lint-amnesty, pylint: disable=imported-auth-user
from django.db import models
from django.utils.translation import gettext_lazy as _
from openedx.core.djangoapps.user_api.errors import AccountValidationError  # pylint: disable=import-error

from nau_openedx_extensions.custom_registration_form.choices import (
    CAE4_CHOICES,
    EMPLOYMENT_SITUATION_CHOICES,
    NUTS_CHOICES,
)
from nau_openedx_extensions.utils.nif import is_nif_valid

# Backwards compatible settings.AUTH_USER_MODEL
USER_MODEL = getattr(settings, "AUTH_USER_MODEL", "auth.User")  # lint-amnesty, pylint: disable=hard-coded-auth-user


class NifValidator:
    """
    NIF Django validator
    """

    def __init__(self, message=None):
        self.message = message or _("Invalid NIF")

    def __call__(self, value):
        if not is_nif_valid(value):
            message = _("Invalid NIF")
            raise AccountValidationError({
                # the 'extended_profile' instead of 'nif' is an hack to show the error in the Django UI
                'extended_profile': {
                    "developer_message": message,
                    "user_message": message,
                }
            })


class NauUserExtendedModel(models.Model):
    """
    Holds data authorization field
    Used during user registration as a form extension.
    """

    user = models.OneToOneField(USER_MODEL, on_delete=models.CASCADE, null=True)
    data_authorization = models.BooleanField(
        verbose_name=_(
            "I have read and understood the <a href='https://www.nau.edu.pt/legal/politica-de-privacidade/' "
            "rel='noopener' target='_blank'>Privacy Policy</a>"
        ), default=False
    )
    nif = models.CharField(
        verbose_name=_("NIF"), max_length=9, blank=True, null=True, validators=[NifValidator()]
    )
    cc_nif = models.CharField(
        verbose_name=_("CC NIF"), max_length=9, blank=True, null=True
    )
    cc_nic = models.CharField(
        verbose_name=_("CC NIC"), max_length=16, blank=True, null=True
    )
    cc_nic_check_digit = models.CharField(
        verbose_name=_("CC NIC Check Digit"), max_length=16, blank=True, null=True
    )
    cc_first_name = models.TextField(
        verbose_name=_("CC First name"), blank=True, null=True
    )
    cc_last_name = models.TextField(verbose_name=_("CC Last name"), blank=True, null=True)
    cc_nationality = models.TextField(
        verbose_name=_("CC Nacionality"), blank=True, null=True
    )
    cc_zip3 = models.CharField(
        verbose_name=_("CC Zip code 3 digits"), max_length=3, blank=True, null=True
    )
    cc_zip4 = models.CharField(
        verbose_name=_("CC Zip code 4 digits"), max_length=4, blank=True, null=True
    )
    cc_doc_number = models.CharField(
        verbose_name=_("CC Document number"), max_length=16, blank=True, null=True
    )
    cc_birth_date = models.CharField(
        verbose_name=_("CC Birth date"), max_length=12, blank=True, null=True
    )
    employment_situation = models.TextField(
        verbose_name=_("Employment situation"), blank=True, null=True, choices=EMPLOYMENT_SITUATION_CHOICES
    )
    nuts = models.CharField(
        verbose_name=_("NUTS II - NUTS III"), max_length=64, blank=True, null=True, choices=NUTS_CHOICES
    )
    cae4 = models.CharField(
        verbose_name=_("CAE4"), max_length=64, blank=True, null=True, choices=CAE4_CHOICES
    )
    allow_newsletter = models.BooleanField(
        verbose_name=_("Allow newsletter"), default=False
    )

    def __str__(self):
        return "<Nau extended data for {}>".format(self.user.username)

    def date_joined(self):
        return self.user.date_joined

    def is_active(self):
        return self.user.is_active

# Add more fields to the student profile download csv file.
#
# This feature requires that additional properties be configured on `STUDENT_FEATURES` list on file
# lms/djangoapps/instructor_analytics/basic.py
#
# Dynamic add properties to the User model so they could be added to the
# `student_profile_download_fields` site configuration


def get_nau_user_extended_model_cc_nic(self):
    """
    Get NauUserExtendedModel portuguese citizen card NIC number - portuguese civil identification.
    """
    if hasattr(self, "nauuserextendedmodel"):
        return self.nauuserextendedmodel.cc_nic
    return None


# lint-amnesty, pylint: disable=literal-used-as-attribute
setattr(User, 'nau_user_extended_model_cc_nic', property(get_nau_user_extended_model_cc_nic))


def get_nau_nif(self):
    """
    Get NIF, Portuguese taxpayer identification number.
    """
    if hasattr(self, "nauuserextendedmodel"):
        nif = self.nauuserextendedmodel.nif
        cc_nif = self.nauuserextendedmodel.cc_nif
        return nif if nif else cc_nif
    return None


setattr(User, 'nau_nif', property(get_nau_nif))  # lint-amnesty, pylint: disable=literal-used-as-attribute


def get_nau_user_extended_model_employment_situation(self):
    """
    Employment situation as its readable label, so reports carry text and not codes.
    """
    if hasattr(self, "nauuserextendedmodel"):
        return self.nauuserextendedmodel.get_employment_situation_display()
    return None


setattr(User, 'nau_user_extended_model_employment_situation', property(
    get_nau_user_extended_model_employment_situation))


def get_nau_user_extended_model_nuts(self):
    """
    NUTS II - NUTS III as its readable label.
    """
    if hasattr(self, "nauuserextendedmodel"):
        return self.nauuserextendedmodel.get_nuts_display()
    return None


setattr(User, 'nau_user_extended_model_nuts', property(  # lint-amnesty, pylint: disable=literal-used-as-attribute
    get_nau_user_extended_model_nuts))


def get_nau_user_extended_model_cae4(self):
    """
    CAE4 as its readable label.
    """
    if hasattr(self, "nauuserextendedmodel"):
        return self.nauuserextendedmodel.get_cae4_display()
    return None


setattr(User, 'nau_user_extended_model_cae4', property(  # lint-amnesty, pylint: disable=literal-used-as-attribute
    get_nau_user_extended_model_cae4))
