"""Factory classes for custom registration form models."""
import factory
from common.djangoapps.student.tests.factories import UserFactory

from nau_openedx_extensions.models import NauUserExtendedModel


class NauUserExtendedModelFactory(factory.django.DjangoModelFactory):
    """
    Factory for NauUserExtendedModel, creating a user automatically if not provided.
    """

    class Meta:
        model = NauUserExtendedModel

    user = factory.SubFactory(UserFactory)
    data_authorization = True
    nif = factory.Sequence(lambda n: f"{n:09d}")
    cc_nif = factory.Sequence(lambda n: f"{n:09d}")
    cc_first_name = factory.LazyAttribute(lambda o: o.user.first_name)
    cc_last_name = factory.LazyAttribute(lambda o: o.user.last_name)
    employment_situation = NauUserExtendedModel.STUDENT
    allow_newsletter = False
