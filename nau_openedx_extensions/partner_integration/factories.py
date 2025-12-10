"""Factory classes for Data Extractor models."""
import factory

from nau_openedx_extensions.partner_integration.models import PartnerAPIClient


class PartnerAPIClientFactory(factory.django.DjangoModelFactory):
    """Factory for PartnerAPIClient"""

    class Meta:
        model = PartnerAPIClient

    name = factory.Sequence(lambda n: f"partner-{n}")
    is_active = True
