"""
Celery tasks for certificate dispatch system.
"""

import requests
from celery import shared_task

from nau_openedx_extensions.coursecertificate.engine import CertificateEngine


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_service_certificates(self, service_config: dict, options: dict) -> dict:
    """
    Process certificates for a specific service asynchronously.

    Args:
        service_config: Configuration for the service
        options: Command options (dry_run, days, page_size, etc.)

    Returns:
        Dict with task results
    """
    service_name = service_config.get("service_name", "unknown")

    try:
        # Create engine instance
        engine = CertificateEngine()

        # Process the service using the engine
        engine.process_service(service_config, options)

        return {
            "task_id": self.request.id,
            "service_name": service_name,
            "status": "success",
        }

    except (ConnectionError, TimeoutError, requests.exceptions.RequestException) as exc:
        # Retry on connection errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=self.default_retry_delay)

        return {
            "task_id": self.request.id,
            "service_name": service_name,
            "status": "error",
            "error": str(exc),
        }
