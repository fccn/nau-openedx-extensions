"""
Send course certificates to external services based on YAML configuration.
"""

import os

import yaml
from django.core.management.base import BaseCommand, CommandError

from nau_openedx_extensions.coursecertificate.engine import CertificateEngine


class Command(BaseCommand):
    """
    Send course certificates to external services based on YAML configuration.
    """

    help = "Send course certificates to external services"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize the engine with our logger
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

    def get_default_config_path(self) -> str:
        """Get default configuration file path"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.dirname(os.path.dirname(current_dir))
        return os.path.join(config_dir, "config.yml")

    def load_config(self, config_path: str) -> list[dict]:
        """Load YAML configuration"""
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                return config.get("NAU_SEND_COURSE_CERTIFICATE_CONFIG", [])
        except FileNotFoundError as exc:
            raise CommandError(f"Configuration file not found: {config_path}") from exc
        except yaml.YAMLError as exc:
            raise CommandError(f"Error parsing YAML configuration: {exc}") from exc

    def log_msg(self, msg: str) -> None:
        """Log a message immediately"""
        self.stdout.write(msg)
        self.stdout.flush()

    def process_service(self, service_config: dict, options: dict) -> None:
        """Process certificates for a specific service using the engine"""
        # Delegate everything to the engine
        self.engine.process_service(service_config, options)

    def handle(self, *args, **options) -> None:
        """Execute the command"""
        dry_run = options.get("dry_run", False)
        async_mode = options.get("async_mode", False)

        if dry_run:
            self.log_msg("=== DRY RUN MODE - No actual requests will be sent ===")

        if async_mode:
            self.log_msg("=== ASYNC MODE - Dispatching services via Celery ===")
            self.handle_async(options)
            return

        # Load configuration
        config_path = options["config"]
        config = self.load_config(config_path)
        self.log_msg(f"Loaded configuration from: {config_path}")

        # Filter services if specific service requested
        target_service = options.get("service_name")
        if target_service:
            services_to_process = [service for service in config if service.get("service_name") == target_service]
            if not services_to_process:
                raise CommandError(f"Service '{target_service}' not found in configuration")
        else:
            services_to_process = config

        self.log_msg(f"Processing {len(services_to_process)} service(s)")

        # Process each service using the engine
        for service_config in services_to_process:
            try:
                self.process_service(service_config, options)
            except (KeyError, ValueError, TypeError) as exc:
                self.log_msg(f"Error processing service {service_config.get('service_name', 'unknown')}: {exc}")
                continue

        self.log_msg("\n=== All services processed ===")

    def handle_async(self, options: dict) -> None:
        """Handle asynchronous execution using Celery"""
        pass
