"""
Send course certificates to external services based on YAML configuration.
"""
import hashlib
import importlib
import os
from datetime import datetime, timedelta

import requests
import yaml
from common.djangoapps.util.query import use_read_replica_if_available
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.paginator import Paginator
from lms.djangoapps.certificates.models import GeneratedCertificate  # can we use wrapper here?
from pytz import UTC


class Command(BaseCommand):
    """
    Send course certificates to external services based on YAML configuration.
    """

    help = "Send course certificates to external services"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = None
        self.dry_run = False
        self.async_mode = False

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
            "--service",
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

    def get_default_config_path(self):
        """Get default configuration file path"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_dir = os.path.dirname(os.path.dirname(current_dir))
        return os.path.join(config_dir, "config.yml")

    def load_config(self, config_path):
        """Load YAML configuration"""
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                return config.get('NAU_SEND_COURSE_CERTIFICATE_CONFIG', [])
        except FileNotFoundError:
            raise CommandError(f"Configuration file not found: {config_path}")
        except yaml.YAMLError as e:
            raise CommandError(f"Error parsing YAML configuration: {e}")

    def log_msg(self, msg):
        """Log a message immediately"""
        self.stdout.write(msg)
        self.stdout.flush()

    def apply_transformations(self, value, trans):
        """Apply transformations to a field value"""
        if trans == "md5":
            return hashlib.md5(str(value).encode()).hexdigest()
        elif trans == "base64":
            import base64
            return base64.b64encode(str(value).encode()).decode()
        return value

    def extract_field_value(self, certificate, field_config):
        """Extract field value from certificate using configured function"""
        func_path = field_config['func']
        args = field_config.get('args', [])
        trans = field_config.get('trans')

        try:
            # Import the function dynamically
            module_path, func_name = func_path.rsplit('.', 1)
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
        except Exception as e:
            self.log_msg(f"Error extracting field {field_config['name']}: {e}")
            return None

    def apply_filters(self, certificates, service_config):
        """Apply filters to certificates based on service configuration"""
        filters = service_config.get('filters', [])
        filtered_certificates = certificates

        for filter_config in filters:
            try:
                func_path = filter_config['func']
                args = filter_config.get('args', [])

                # Import the filter function dynamically
                module_path, func_name = func_path.rsplit('.', 1)
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

            except Exception as e:
                self.log_msg(f"Error applying filter {filter_config['func']}: {e}")
                continue

        return filtered_certificates

    def convert_certificates_to_service_format(self, certificates, service_config):
        """Convert certificates to the format required by the service"""
        fields_config = service_config.get('fields', [])
        converted_data = []

        for certificate in certificates:
            cert_data = {}
            for field_config in fields_config:
                field_name = field_config['name']
                field_value = self.extract_field_value(certificate, field_config)
                if field_value is not None:
                    cert_data[field_name] = field_value

            if cert_data:  # Only add if we have data
                converted_data.append(cert_data)

        return converted_data

    def send_certificates_to_service(self, service_config, certificates_data):
        """Send certificates to external service"""
        service_name = service_config['service']
        api_url = service_config.get('endpoint_url')
        auth_token = service_config.get('auth_token')
        auth_type = service_config.get('auth_type', 'bearer')
        auth_header = service_config.get('auth_header', 'Authorization')

        self.log_msg(f"Sending {len(certificates_data)} certificates to {service_name}")
        self.log_msg(f"Data: {certificates_data}")

        if self.dry_run:
            self.log_msg(f"[DRY RUN] Would send to {api_url}")
            self.log_msg(f"[DRY RUN] Headers would include: {auth_type} authentication")
            self.log_msg(f"[DRY RUN] Auth header: {auth_header}")
            return True

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
                import base64
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

        except requests.RequestException as e:
            self.log_msg(f"Request error sending to {service_name}: {e}")
            return False

    def get_certificates_queryset(self, days):
        """Get certificates queryset filtered by date"""
        begin_date = datetime.now(UTC) - timedelta(days=days)
        return use_read_replica_if_available(
            GeneratedCertificate.objects.filter(created_date__gte=begin_date)
            .order_by("created_date")
            .select_related("user")
        )

    def process_service(self, service_config, options):
        """Process certificates for a specific service"""
        service_name = service_config['service']
        self.log_msg(f"\n=== Processing service: {service_name} ===")

        # Determine days to process
        days = options.get('days')
        if days is None:
            days = service_config.get('days_back', 7)

        # Determine page size
        page_size = options.get('page_size')
        if page_size is None:
            page_size = service_config.get('batch_size', 1000)

        self.log_msg(f"Processing certificates from last {days} days")
        self.log_msg(f"Batch size: {page_size}")

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
            certificates = list(page.object_list)
            processed_count += len(certificates)

            self.log_msg(f"Processing {processed_count} of {total_count} certificates")

            if certificates:
                # Convert to service format
                certificates_data = self.convert_certificates_to_service_format(
                    certificates, service_config
                )

                if certificates_data:
                    # Send to service
                    success = self.send_certificates_to_service(service_config, certificates_data)
                    if not success:
                        self.log_msg(f"Failed to send batch {page_num} to {service_name}")

        self.log_msg(f"Finished processing {service_name}")

    def handle(self, *args, **options):
        """Execute the command"""
        self.dry_run = options.get('dry_run', False)
        self.async_mode = options.get('async_mode', False)

        if self.dry_run:
            self.log_msg("=== DRY RUN MODE - No actual requests will be sent ===")

        if self.async_mode:
            self.log_msg("=== ASYNC MODE - Would run via Celery (not implemented yet) ===")
            # TODO: Implement Celery integration
            return

        # Load configuration
        config_path = options.get('config')
        self.config = self.load_config(config_path)
        self.log_msg(f"Loaded configuration from: {config_path}")

        # Filter services if specific service requested
        target_service = options.get('service')
        if target_service:
            services_to_process = [
                service for service in self.config
                if service.get('service') == target_service
            ]
            if not services_to_process:
                raise CommandError(f"Service '{target_service}' not found in configuration")
        else:
            services_to_process = self.config

        self.log_msg(f"Processing {len(services_to_process)} service(s)")

        # Process each service
        for service_config in services_to_process:
            try:
                self.process_service(service_config, options)
            except Exception as e:
                self.log_msg(f"Error processing service {service_config.get('service', 'unknown')}: {e}")
                continue

        self.log_msg("\n=== All services processed ===")
