"""
Send course certificates to external services based on YAML configuration.
"""

import base64
import hashlib
import importlib
import json
import os
from datetime import datetime, timedelta

import requests
import yaml
from django.core.management.base import BaseCommand, CommandError
from django.core.paginator import Paginator
from django.db.models import QuerySet
from pytz import UTC

from nau_openedx_extensions.edxapp_wrapper.certificates import GeneratedCertificate
from nau_openedx_extensions.edxapp_wrapper.util import use_read_replica_if_available


class Command(BaseCommand):
    """
    Send course certificates to external services based on YAML configuration.
    """

    help = "Send course certificates to external services"

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

    def apply_transformations(self, value: str, trans: str) -> str:
        """Apply transformations to a field value"""
        if trans == "md5":
            return hashlib.md5(str(value).encode()).hexdigest()
        elif trans == "base64":
            return base64.b64encode(str(value).encode()).decode()
        return value

    def extract_field_value(self, certificate: QuerySet, field_config: dict) -> str | None:
        """Extract field value from certificate using configured function"""
        func_path = field_config["func"]
        args = field_config.get("args", [])
        trans = field_config.get("trans")

        try:
            # Import the function dynamically
            module_path, func_name = func_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            extract_func = getattr(module, func_name)

            # Call the function with certificate and args
            if args:
                if isinstance(args, list):
                    value = extract_func(certificate, *args)
                else:
                    value = extract_func(certificate, args)
            else:
                value = extract_func(certificate)

            # Apply transformations if specified
            if trans:
                value = self.apply_transformations(value, trans)

            return value
        except (ImportError, AttributeError, TypeError) as exc:
            self.log_msg(f"Error extracting field {field_config['name']}: {exc}")
            return None

    def apply_filters(self, certificates: QuerySet, service_config: dict) -> QuerySet:
        """Apply filters to certificates based on service configuration"""
        filters = service_config.get("filters", [])
        filtered_certificates = certificates

        for filter_config in filters:
            try:
                func_path = filter_config["func"]
                args = filter_config.get("args", [])

                # Import the filter function dynamically
                module_path, func_name = func_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                filter_func = getattr(module, func_name)

                # Apply the filter
                if args:
                    if isinstance(args, list):
                        filtered_certificates = filter_func(filtered_certificates, *args)
                    else:
                        filtered_certificates = filter_func(filtered_certificates, args)
                else:
                    filtered_certificates = filter_func(filtered_certificates)

            except (ImportError, AttributeError, TypeError) as exc:
                self.log_msg(f"Error applying filter {filter_config['func']}: {exc}")
                continue

        return filtered_certificates

    def convert_certificates_to_service_format(self, certificates: QuerySet, service_config: dict) -> list[dict]:
        """Convert certificates to the format required by the service"""
        fields_config = service_config.get("fields", [])
        converted_data = []

        for certificate in certificates:
            cert_data = {}
            for field_config in fields_config:
                field_name = field_config["name"]
                field_value = self.extract_field_value(certificate, field_config)
                if field_value is not None:
                    cert_data[field_name] = field_value

            if cert_data:  # Only add if we have data
                converted_data.append(cert_data)

        return converted_data

    def send_certificates_to_service(self, service_config: dict, certificates_data: list[dict], dry_run: bool = False) -> bool:  #pylint: disable=line-too-long
        """Send certificates to external service"""
        service_name = service_config["service_name"]
        api_url = service_config["endpoint_url"]
        auth_token = service_config.get("auth_token")
        auth_type = service_config.get("auth_type", "bearer")
        auth_header = service_config.get("auth_header", "Authorization")

        if dry_run:
            self.log_msg(f"[DRY RUN] Would send to {api_url}")
            self.log_msg(f"[DRY RUN] Headers would include: {auth_type} authentication")
            self.log_msg(f"[DRY RUN] Auth header: {auth_header}")
            self.log_msg("[DRY RUN] Payload:")
            self.log_msg(json.dumps(certificates_data, indent=2, ensure_ascii=False))
            return True
        else:
            self.log_msg(f"Sending {len(certificates_data)} certificates to {service_name}")
            self.log_msg(f"Data: {certificates_data}")

        # Prepare headers
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Handle different authentication types
        if auth_token:
            if auth_type == "bearer":
                headers[auth_header] = f"Bearer {auth_token}"
            elif auth_type == "basic":
                credentials = base64.b64encode(auth_token.encode()).decode()
                headers[auth_header] = f"Basic {credentials}"
            elif auth_type == "api_key":
                headers[auth_header] = auth_token
            else:
                # Custom auth type - use as-is
                headers[auth_header] = f"{auth_type} {auth_token}"

        try:
            response = requests.post(
                api_url,
                json=certificates_data,
                headers=headers,
                timeout=60,
            )

            if response.ok:
                self.log_msg(f"Certificates sent successfully to {service_name}")
                return True
            else:
                self.log_msg(f"Failed to send certificates to {service_name}: {response.text}")
                return False

        except requests.RequestException as exc:
            self.log_msg(f"Request error sending to {service_name}: {exc}")
            return False

    def get_certificates_queryset(self, days: int) -> QuerySet:
        """Get certificates queryset filtered by date"""
        begin_date = datetime.now(UTC) - timedelta(days=days)
        return use_read_replica_if_available(
            GeneratedCertificate.objects.filter(created_date__gte=begin_date)
            .order_by("created_date")
            .select_related("user")
        )

    def process_service(self, service_config: dict, options: dict) -> None:
        """Process certificates for a specific service"""
        service_name = service_config.get("service_name")
        self.log_msg(f"\n=== Processing service: {service_name} ===")

        # Get dry_run from options
        dry_run = options.get("dry_run", False)

        # Determine days to process
        days = options.get("days")
        if days is None:
            days = service_config.get("days", 7)

        # Determine page size
        page_size = options.get("page_size")
        if page_size is None:
            page_size = service_config.get("page_size", 1000)

        self.log_msg(f"Processing certificates from the last {days} days")
        self.log_msg(f"Page size: {page_size}")

        # Get certificates
        certificates_queryset = self.get_certificates_queryset(days)

        # Apply service-specific filters
        certificates_queryset = self.apply_filters(certificates_queryset, service_config)

        # Paginate and process
        paginator = Paginator(certificates_queryset, page_size)
        total_count = paginator.count
        processed_count = 0

        self.log_msg(f"Total certificates to process: {total_count}")

        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            certificates = page.object_list
            processed_count += len(certificates)

            self.log_msg(f"Processing {processed_count} of {total_count} certificates")

            if certificates:
                # Convert to service format
                certificates_data = self.convert_certificates_to_service_format(certificates, service_config)

                if certificates_data:
                    # Send to service - PASAR dry_run como parámetro
                    success = self.send_certificates_to_service(service_config, certificates_data, dry_run)
                    if not success:
                        self.log_msg(f"Failed to send page {page_num} to {service_name}")

        self.log_msg(f"Finished processing {service_name}")

    def handle(self, *args, **options) -> None:
        """Execute the command"""
        dry_run = options.get("dry_run", False)
        async_mode = options.get("async_mode", False)

        if dry_run:
            self.log_msg("=== DRY RUN MODE - No actual requests will be sent ===")

        if async_mode:
            self.log_msg("=== ASYNC MODE - Would run via Celery (not implemented yet) ===")
            # TODO: Implement Celery integration
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

        # Process each service
        for service_config in services_to_process:
            try:
                self.process_service(service_config, options)
            except (KeyError, ValueError, TypeError) as exc:
                self.log_msg(f"Error processing service {service_config.get('service_name', 'unknown')}: {exc}")
                continue

        self.log_msg("\n=== All services processed ===")
