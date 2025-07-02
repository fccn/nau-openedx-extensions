"""
Send course certificates to external services based on YAML configuration.
"""

import os
from typing import Any, Optional

import yaml
from django.core.management.base import BaseCommand, CommandError

from nau_openedx_extensions.coursecertificate.engine import CertificateEngine


class Command(BaseCommand):
    """
    Send course certificates to external services based on YAML configuration.
    """

    help = "Send course certificates to external services"

    DEFAULT_CONFIG_FILENAME = "config.yml"
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
            "--config",
            default=self.get_default_config_path(),
            help="Path to YAML configuration file",
        )
        parser.add_argument(
            "--service-name",
            help="Specific service to send certificates to (from config)",
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
            help="Run via Celery (for milestone 3 compatibility)",
        )

    def log_msg(self, msg: str) -> None:
        """Log a message immediately"""
        self.stdout.write(msg)
        self.stdout.flush()

    def get_default_config_path(self) -> str:
        """Get default configuration file path"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.dirname(os.path.dirname(current_dir))
        return os.path.join(config_dir, self.DEFAULT_CONFIG_FILENAME)

    def load_config(self, config_path: str) -> list[dict]:
        """Load YAML configuration"""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                return config.get(self.CONFIG_KEY, [])
        except FileNotFoundError as exc:
            raise CommandError(f"Configuration file not found: {config_path}") from exc
        except yaml.YAMLError as exc:
            raise CommandError(f"Error parsing YAML configuration: {exc}") from exc

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
        config = self.load_config(options["config"])
        services_to_process = self.filter_services(config, options.get("service_name"))

        self.log_msg(f"Loaded configuration from: {options['config']}")
        self.log_msg(f"Processing {len(services_to_process)} service(s)")

        success_count = 0
        for service_config in services_to_process:
            if self.process_service_safely(service_config, options):
                success_count += 1

        self.log_msg(f"\n{self.MSG_ALL_PROCESSED}")
        self.log_msg(f"Successfully processed {success_count}/{len(services_to_process)} services.")

    def handle_async(self, options: dict) -> None:
        """Handle asynchronous execution using Celery"""
        raise CommandError("Async mode is not yet implemented. Use without --async flag.")
