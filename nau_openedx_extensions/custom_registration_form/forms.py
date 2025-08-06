"""
Nau openedx extension custom forms module
"""

from __future__ import absolute_import, unicode_literals

from django import forms
from django.forms import ModelForm
from django.utils.translation import gettext as _

from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel
from nau_openedx_extensions.utils.nif import is_nif_valid


def validate_nif(value: str) -> None:
    """
    Validate the nif according to the `is_nif_valid` function.
    """
    if not is_nif_valid(value):
        raise forms.ValidationError(_("Invalid NIF"))


class NauUserExtendedForm(ModelForm):
    """
    This form extends the user registration form
    """

    class Meta:
        model = NauUserExtendedModel
        fields = [
            "data_authorization",
            "cc_nif",
            "cc_nic",
            "cc_nic_check_digit",
            "cc_first_name",
            "cc_last_name",
            "cc_nationality",
            "cc_zip3",
            "cc_zip4",
            "cc_doc_number",
            "cc_birth_date",
            "employment_situation",
            "allow_newsletter",
            "nif",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_authorization"].error_messages = {
            "required": _("You must read and understood the Privacy Policy")
        }
        self.fields["nif"].validators = [validate_nif]
