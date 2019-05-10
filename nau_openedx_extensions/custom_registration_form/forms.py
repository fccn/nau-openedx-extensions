from django.forms import ModelForm
from django.utils.translation import ugettext as _
from nau_openedx_extensions.custom_registration_form.models import NauUserExtendedModel


class NauUserExtendedForm(ModelForm):
    """
    This form extends the user registration form
    """
    class Meta(object):
        model = NauUserExtendedModel
        fields = [
            'data_authorization',
            'citizen_card',
            'nif',
        ]

    def __init__(self, *args, **kwargs):
        super(NauUserExtendedForm, self).__init__(*args, **kwargs)
        self.fields['data_authorization'].error_messages = {
            "required": _('Please authorize data processing')
        }

