"""Factory classes for Data Extractor models."""
import factory
from common.djangoapps.student.tests.factories import UserFactory

from nau_openedx_extensions.partner_integration.models import PartnerAPIClient, SSOPartnerIntegration


class PartnerAPIClientFactory(factory.django.DjangoModelFactory):
    """Factory for PartnerAPIClient"""

    class Meta:
        model = PartnerAPIClient

    name = factory.Sequence(lambda n: f"partner-{n}")
    is_active = True


class SSOPartnerIntegrationFactory(factory.django.DjangoModelFactory):
    """Factory for SSOPartnerIntegration"""

    class Meta:
        model = SSOPartnerIntegration

    partner_client = factory.SubFactory(PartnerAPIClientFactory)
    user = factory.SubFactory(UserFactory)
    external_user_id = factory.Sequence(lambda n: f"external-user-{n}")
