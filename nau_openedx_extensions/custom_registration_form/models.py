"""
Models for Nau extended user
"""

from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

# Backwards compatible settings.AUTH_USER_MODEL
USER_MODEL = getattr(settings, "AUTH_USER_MODEL", "auth.User")


class NauUserExtendedModel(models.Model):
    """
    Holds data autorization field
    Used during user registration as a form extension.
    """

    STUDENT='Student'
    UNEMPLOYED='Unemployed'
    PUBLIC_SERVICE_CONTRACT='Public service contract'
    PRIVATE_INSTITUTION_CONTRACT='Private institution contract'
    SELF_EMPLOYED='Self employed entrepreneur'
    OTHER='Other'

    EMPLOYMENT_SITUATION_CHOICES = [
        (STUDENT, _('Student')),
        (UNEMPLOYED, _('Unemployed')),
        (PUBLIC_SERVICE_CONTRACT, _('Public service contract')),
        (PRIVATE_INSTITUTION_CONTRACT, _('Private institution contract')),
        (SELF_EMPLOYED, _('Self employed entrepreneur')),
        (OTHER, _('Other'))
    ]

    user = models.OneToOneField(USER_MODEL, on_delete=models.CASCADE, null=True)
    data_authorization = models.BooleanField(
        verbose_name=_("I authorize data processing for this site "), default=False
    )
    cc_nif = models.CharField(
        verbose_name=_("NIF"), max_length=9, blank=True, null=True
    )
    cc_nic = models.CharField(
        verbose_name=_("NIC"), max_length=16, blank=True, null=True
    )
    cc_nic_check_digit = models.CharField(
        verbose_name=_("NIC Check Digit"), max_length=16, blank=True, null=True
    )
    cc_first_name = models.TextField(
        verbose_name=_("First name"), blank=True, null=True
    )
    cc_last_name = models.TextField(verbose_name=_("Last name"), blank=True, null=True)
    cc_nationality = models.TextField(
        verbose_name=_("Nacionality"), blank=True, null=True
    )
    cc_zip3 = models.CharField(
        verbose_name=_("Zip code 3 digits"), max_length=3, blank=True, null=True
    )
    cc_zip4 = models.CharField(
        verbose_name=_("Zip code 4 digits"), max_length=4, blank=True, null=True
    )
    cc_doc_number = models.CharField(
        verbose_name=_("Document number"), max_length=16, blank=True, null=True
    )
    cc_birth_date = models.CharField(
        verbose_name=_("Birth date"), max_length=12, blank=True, null=True
    )
    employment_situation = models.TextField(
        verbose_name=_("Employment situation"), blank=True, null=True, choices=EMPLOYMENT_SITUATION_CHOICES
    )
    allow_newsletter = models.BooleanField(
        verbose_name=_("Allow newsletter"), default=False
    )

    def __unicode__(self):
        return "<Nau extended data for {}>".format(self.user.username)

    def date_joined(self):
        return self.user.date_joined

# Add more fields to the student profile download csv file.
#
# This feature requires that additional properties be configured on `STUDENT_FEATURES` list on file
# lms/djangoapps/instructor_analytics/basic.py
# 
# Dynamic add properties to the User model so they could be added to the `student_profile_download_fields` site configuration
from django.contrib.auth.models import User

def get_nau_user_extended_model_cc_nic(self):
    if hasattr(self, "nauuserextendedmodel"):
        return self.nauuserextendedmodel.cc_nic
    return None
setattr(User, 'nau_user_extended_model_cc_nic', property(get_nau_user_extended_model_cc_nic))

def get_nau_user_extended_model_cc_nif(self):
    if hasattr(self, "nauuserextendedmodel"):
        return self.nauuserextendedmodel.cc_nif
    return None
setattr(User, 'nau_user_extended_model_cc_nif', property(get_nau_user_extended_model_cc_nif))

def get_nau_user_extended_model_employment_situation(self):
    if hasattr(self, "nauuserextendedmodel"):
        return self.nauuserextendedmodel.employment_situation
    return None
setattr(User, 'nau_user_extended_model_employment_situation', property(get_nau_user_extended_model_employment_situation))
