"""
Send course certificates to external services based on YAML configuration.

NOTE: The NAU_SEND_COURSE_CERTIFICATE_CONFIG setting comes from Django setting.
"""

from typing import Any, Optional

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from nau_openedx_extensions.coursecertificate.engine import CertificateEngine
from nau_openedx_extensions.coursecertificate.tasks import process_service_certificates


class Command(BaseCommand):
    """
    Send course certificates to external services based on the
    Djando setting `NAU_SEND_COURSE_CERTIFICATE_CONFIG`.
    """

    help = """
    Send course certificates to external services configured
    in the Djando setting `NAU_SEND_COURSE_CERTIFICATE_CONFIG`.
    """

    CONFIG_KEY = "NAU_SEND_COURSE_CERTIFICATE_CONFIG"

    MSG_DRY_RUN = "=== DRY RUN MODE - No actual requests will be sent ==="
    MSG_ASYNC_MODE = "=== ASYNC MODE - Dispatching services via Celery ==="
    MSG_ALL_PROCESSED = "=== All services processed ==="

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = CertificateEngine(logger=self.log_msg)

    def add_arguments(self, parser):
        """
        Configure Django Command arguments
        """
        parser.add_argument(
            "--service-name",
            help="Specific service to send certificates to (from config)",
        )
        parser.add_argument(
            "--certificate-id",
            type=int,
            help="Process only the certificate with this specific ID",
        )
        parser.add_argument(
            "--days",
            type=int,
            help="Number of days of certificates to process",
        )
        parser.add_argument(
            "--page-size",
            type=int,
            help="Number of certificates per batch",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate dispatch without sending HTTP requests",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="async_mode",
            help="Run via Celery (asynchronous mode)",
        )

    def log_msg(self, msg: str) -> None:
        """Log a message immediately"""
        self.stdout.write(msg)
        self.stdout.flush()

    def load_config(self) -> list[dict]:
        """Load configuration from Django settings"""
        config = getattr(settings, self.CONFIG_KEY, None)
        if config is None:
            raise CommandError(
                f"Configuration setting '{self.CONFIG_KEY}' not found in Django settings. "
                "This setting comes from Tutor configuration."
            )
        if not isinstance(config, list):
            raise CommandError(
                f"Configuration setting '{self.CONFIG_KEY}' must be a list of service configurations."
            )
        return config

    def process_service_safely(self, service_config: dict[str, Any], options: dict[str, Any]) -> bool:
        """Process a service with proper error handling"""
        service_name = service_config.get("service_name", "unknown")

        try:
            self.engine.process_service(service_config, options)
            self.log_msg(f"✓ Successfully processed service: {service_name}.")
            return True
        except (KeyError, ValueError, TypeError) as exc:
            self.log_msg(f"Configuration error for service {service_name}: {exc}")
            return False
        except Exception as exc:  # pylint: disable=broad-except
            self.log_msg(f"Unexpected error processing service {service_name}: {exc}")
            return False

    def dispatch_service_task_safely(self, service_config: dict[str, Any], options: dict[str, Any]) -> Optional[dict]:
        """Dispatch a service task with proper error handling"""
        service_name = service_config.get("service_name", "unknown")

        try:
            # Dispatch the task
            task = process_service_certificates.delay(service_config, options)
            self.log_msg(f"[DISPATCH] Task dispatched for service '{service_name}'")

            return {
                "service_name": service_name,
                "task_id": task.id
            }

        except (ConnectionError, TimeoutError, ValueError, TypeError) as exc:
            self.log_msg(f"[ERROR] Failed to dispatch task for service '{service_name}': {exc}")
            return None
        except Exception as exc:  # pylint: disable=broad-except
            self.log_msg(f"[ERROR] Unexpected error dispatching task for service '{service_name}': {exc}")
            return None

    def filter_services(self, config: list[dict[str, Any]], target_service: Optional[str]) -> list[dict[str, Any]]:
        """Filter services based on target service name"""
        if not target_service:
            return config

        services = [service for service in config if service.get("service_name") == target_service]
        if not services:
            raise CommandError(f"Service '{target_service}' not found in configuration.")

        return services

    def handle(self, *args, **options) -> None:
        """Execute the command"""
        if options.get("dry_run", False):
            self.log_msg(self.MSG_DRY_RUN)

        if options.get("async_mode", False):
            self.log_msg(self.MSG_ASYNC_MODE)
            return self.handle_async(options)

        return self.handle_sync(options)

    def handle_sync(self, options: dict[str, Any]) -> None:
        """Handle synchronous execution"""
        config = self.load_config()
        services_to_process = self.filter_services(config, options.get("service_name"))

        self.log_msg("Loaded configuration from Django settings")
        self.log_msg(f"Processing {len(services_to_process)} service(s)")

        success_count = 0
        for service_config in services_to_process:
            if self.process_service_safely(service_config, options):
                success_count += 1

        self.log_msg(f"\n{self.MSG_ALL_PROCESSED}")
        self.log_msg(f"Successfully processed {success_count}/{len(services_to_process)} services.")

    def handle_async(self, options: dict) -> None:
        """Handle asynchronous execution using Celery"""

        # Load configuration from Django settings
        config = self.load_config()
        self.log_msg("Loaded configuration from Django settings")

        # Filter services if specific service requested
        services_to_process = self.filter_services(config, options.get("service_name"))

        self.log_msg(f"[INFO] Dispatching {len(services_to_process)} service(s) to Celery background queue")

        # Dispatch each service as a separate Celery task
        dispatched_tasks = []

        for service_config in services_to_process:
            task_info = self.dispatch_service_task_safely(service_config, options)
            if task_info:
                dispatched_tasks.append(task_info)

        # Summary
        successful_dispatches = len(dispatched_tasks)
        total_services = len(services_to_process)

        self.log_msg("\n[DISPATCH] Task Dispatch Summary:")
        self.log_msg(f"[SUCCESS] Successfully dispatched: {successful_dispatches}/{total_services} tasks")

        if dispatched_tasks:
            self.log_msg("   Active tasks:")
            for task_info in dispatched_tasks:
                self.log_msg(f"     • {task_info['service_name']}: {task_info['task_id']}")

        if successful_dispatches < total_services:
            self.log_msg(f"   Failed to dispatch: {total_services - successful_dispatches} tasks")

        self.log_msg("\n Note: Tasks are now running in background. Check Celery logs for execution results.")
