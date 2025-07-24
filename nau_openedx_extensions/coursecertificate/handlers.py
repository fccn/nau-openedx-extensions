"""
Course certificate event handlers.
"""

import logging

from django.core.management import call_command
from django.dispatch import receiver
from openedx_events.data import EventsMetadata
from openedx_events.learning.data import CertificateData
from openedx_events.learning.signals import CERTIFICATE_CREATED
from openedx_events.tooling import OpenEdxPublicSignal

from nau_openedx_extensions.edxapp_wrapper.certificates import GeneratedCertificate

log = logging.getLogger(__name__)


# pylint: disable=unused-argument
@receiver(CERTIFICATE_CREATED)
def certificate_created_send_to_external_services_handler(
    signal: OpenEdxPublicSignal, sender, certificate: CertificateData, metadata: EventsMetadata, **kwargs
):
    """
    Event handler that automatically sends newly created certificates to external services.

    This handler is triggered when a certificate is created in the system. It retrieves
    the corresponding GeneratedCertificate from the database and sends it to all
    configured external services using the send_certificates_by_web_service command.

    Args:
        signal (OpenEdxPublicSignal): The signal that was sent.
        sender: The sender of the signal.
        certificate (CertificateData): The certificate data associated with the event.
        metadata (EventsMetadata): The metadata of the event.
        **kwargs: Additional keyword arguments.
    """
    user_id = certificate.user.id
    course_id = certificate.course.course_key

    try:
        certificate_object = GeneratedCertificate.objects.get(user_id=user_id, course_id=course_id)
    except GeneratedCertificate.DoesNotExist:
        log.error(f"No GeneratedCertificate found for user_id={user_id} and course_id={course_id}")
        return

    log.info(f"Sending certificate {certificate_object.id} to external services")

    try:
        call_command("send_certificates_by_web_service", certificate_id=certificate_object.id, async_mode=True)
    except Exception as e:  # pylint: disable=broad-except
        log.error(f"Failed to send certificate {certificate_object.id} to external services: {e}", exc_info=True)
