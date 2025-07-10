"""
Certificate processing engine - Contains all business logic.
"""

import base64
import hashlib
import importlib
import json
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

import requests
from django.core.paginator import Paginator
from django.db.models import QuerySet
from pytz import UTC

from nau_openedx_extensions.edxapp_wrapper.certificates import GeneratedCertificate
from nau_openedx_extensions.edxapp_wrapper.util import use_read_replica_if_available


class CertificateEngine:
    """
    Certificate processing engine - handles all business logic.
    Independent of Django commands and Celery tasks.
    """

    VALID_AUTH_TYPES = ["bearer", "basic", "api_key"]

    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        """
        Initialize the engine with an optional logger function.

        Args:
            logger: Function to log messages (defaults to print)
        """
        self.log = logger or print

    def apply_transformations(self, value: str, trans: str) -> str:
        """Apply transformations to a field value"""
        transformations = {
            "md5": lambda v: hashlib.md5(str(v).encode()).hexdigest(),
            "base64": lambda v: base64.b64encode(str(v).encode()).decode(),
        }
        transform_func = transformations.get(trans)
        if transform_func:
            return transform_func(value)
        return str(value)

    def extract_field_value(self, certificate: QuerySet, field_config: dict) -> Optional[str]:
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
            self.log(f"Error extracting field {field_config['name']}: {exc}")
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
                self.log(f"Error applying filter {filter_config['func']}: {exc}")
                continue

        return filtered_certificates

    def convert_certificates_to_service_format(self, certificates: QuerySet, service_config: dict) -> List[Dict]:
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

    def send_certificates_to_service(
        self,
        service_config: dict,
        certificates_data: List[Dict],
        dry_run: bool = False
    ) -> bool:
        """Send certificates to external service"""
        service_name = service_config["service_name"]
        api_url = service_config["endpoint_url"]
        auth_token = service_config.get("auth_token")
        auth_type = service_config.get("auth_type", "bearer")
        auth_header = service_config.get("auth_header", "Authorization")

        # Validate auth_type strictly
        if auth_type not in self.VALID_AUTH_TYPES:
            raise ValueError(
                f"Invalid auth_type '{auth_type}' for service '{service_name}'. "
                f"Valid options: {', '.join(self.VALID_AUTH_TYPES)}"
            )

        if dry_run:
            self.log(f"[DRY RUN] Would send to {api_url}")
            self.log(f"[DRY RUN] Headers would include: {auth_type} authentication")
            self.log(f"[DRY RUN] Auth header: {auth_header}")
            self.log(f"[DRY RUN] Auth token: {'Configured' if auth_token else 'Not configured'}")
            self.log("[DRY RUN] Payload:")
            self.log(json.dumps(certificates_data, indent=2, ensure_ascii=False))
            return True

        self.log(f"Sending {len(certificates_data)} certificates to {service_name}")
        self.log(f"Data: {certificates_data}")

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

        try:
            response = requests.post(
                api_url,
                json=certificates_data,
                headers=headers,
                timeout=60,
            )

            if response.ok:
                self.log(f"Certificates sent successfully to {service_name}")
                return True

            self.log(f"Failed to send certificates to {service_name}: {response.text}")
            return False

        except requests.RequestException as exc:
            self.log(f"Request error sending to {service_name}: {exc}")
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
        """
        Process certificates for a specific service.
        This is the main entry point for the business logic.
        """
        service_name = service_config.get("service_name")
        self.log(f"\n=== Processing service: {service_name} ===")

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

        self.log(f"Processing certificates from the last {days} days")
        self.log(f"Page size: {page_size}")

        # Get certificates
        certificates_queryset = self.get_certificates_queryset(days)

        # Apply service-specific filters
        certificates_queryset = self.apply_filters(certificates_queryset, service_config)

        # Paginate and process
        paginator = Paginator(certificates_queryset, page_size)
        total_count = paginator.count
        processed_count = 0

        self.log(f"Total certificates to process: {total_count}")

        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            certificates = page.object_list
            processed_count += len(certificates)

            self.log(f"Processing {processed_count} of {total_count} certificates")

            if certificates:
                # Convert to service format
                certificates_data = self.convert_certificates_to_service_format(certificates, service_config)

                if certificates_data:
                    # Send to service
                    success = self.send_certificates_to_service(service_config, certificates_data, dry_run)
                    if not success:
                        self.log(f"Failed to send page {page_num} to {service_name}")

        self.log(f"Finished processing {service_name}")
