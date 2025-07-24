"""
Certificate processing engine.

This module provides a comprehensive certificate processing engine that handles
the extraction, transformation, and delivery of course certificates to external
services. It includes functionality for filtering certificates, applying data
transformations, and sending them to configured endpoints with various
authentication methods.

The engine is designed to be independent of Django commands and Celery tasks,
making it easily testable and reusable across different contexts.

Classes:
    CertificateEngine: Main engine class that handles all certificate processing logic.
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

    This engine provides a complete solution for processing course certificates
    and sending them to external services. It supports multiple authentication
    methods, data transformations, filtering, and paginated processing.

    The engine is designed to be independent of Django commands and Celery tasks,
    making it easily testable and reusable across different contexts.

    Attributes:
        VALID_AUTH_TYPES (List[str]): Supported authentication types.
        log (Callable[[str], None]): Logger function for output messages.
    """

    VALID_AUTH_TYPES = ["bearer", "basic", "api_key"]

    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        """
        Initialize the engine with an optional logger function.

        Args:
            logger (Optional[Callable[[str], None]]): Function to log messages.
                If not provided, defaults to print function.
        """
        self.log = logger or print

    def _transform_md5(self, value: str) -> str:
        """
        Transform value using MD5 hash.

        Args:
            value (str): The value to transform.

        Returns:
            str: MD5 hash of the input value as hexadecimal string.
        """
        return hashlib.md5(str(value).encode()).hexdigest()

    def _transform_base64(self, value: str) -> str:
        """
        Transform value using Base64 encoding.

        Args:
            value (str): The value to transform.

        Returns:
            str: Base64 encoded string of the input value.
        """
        return base64.b64encode(str(value).encode()).decode()

    def apply_transformations(self, value: str, trans: str) -> str:
        """
        Apply transformations to a field value.

        Supports MD5 hash and Base64 encoding transformations.
        The transformation type is case-insensitive and leading whitespace is stripped.

        Args:
            value (str): The value to transform.
            trans (str): The transformation type ('MD5' or 'BASE64').

        Returns:
            str: The transformed value.

        Raises:
            ValueError: If the transformation type is not supported.
        """
        transformations = {
            "MD5": self._transform_md5,
            "BASE64": self._transform_base64,
        }

        transform_func = transformations.get(trans.strip().upper())
        if transform_func:
            return transform_func(value)
        raise ValueError(f"Encryption method not valid: {trans}")

    def extract_field_value(self, certificate: QuerySet, field_config: dict) -> Optional[str]:
        """
        Extract field value from certificate using configured function.

        Dynamically imports and calls the extraction function specified in the field
        configuration. Supports passing arguments to the function and applying
        transformations to the result.

        Args:
            certificate (QuerySet): The certificate object to extract data from.
            field_config (dict): Configuration dictionary containing:
                - func (str): Module path and function name (e.g., 'module.function')
                - args (list, optional): Arguments to pass to the function
                - trans (str, optional): Transformation to apply to the result
                - name (str): Field name for error reporting

        Returns:
            Optional[str]: The extracted and optionally transformed field value,
                or None if extraction fails.
        """
        func_path = field_config["func"]
        args = field_config.get("args", [])
        trans = field_config.get("trans")

        try:
            module_path, func_name = func_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            extract_func = getattr(module, func_name)

            if args:
                if isinstance(args, list):
                    value = extract_func(certificate, *args)
                else:
                    value = extract_func(certificate, args)
            else:
                value = extract_func(certificate)

            if trans:
                value = self.apply_transformations(value, trans)

            return value
        except (ImportError, AttributeError, TypeError) as exc:
            self.log(f"Error extracting field {field_config['name']}: {exc}")
            return None

    def apply_filters(self, certificates: QuerySet, service_config: dict) -> QuerySet:
        """
        Apply filters to certificates based on service configuration.

        Dynamically imports and applies filter functions specified in the service
        configuration. Each filter function receives the certificates queryset and
        optional arguments, and returns a filtered queryset.

        Args:
            certificates (QuerySet): The certificates queryset to filter.
            service_config (dict): Service configuration containing:
                - filters (list, optional): List of filter configurations, each containing:
                    - func (str): Module path and function name
                    - args (list, optional): Arguments to pass to the filter function

        Returns:
            QuerySet: The filtered certificates queryset.
        """
        filters = service_config.get("filters", [])
        filtered_certificates = certificates

        for filter_config in filters:
            try:
                func_path = filter_config["func"]
                args = filter_config.get("args", [])

                module_path, func_name = func_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                filter_func = getattr(module, func_name)

                if args:
                    if isinstance(args, list):
                        filtered_certificates = filter_func(filtered_certificates, *args)  # pragma: no cover
                    else:
                        filtered_certificates = filter_func(filtered_certificates, args)
                else:
                    filtered_certificates = filter_func(filtered_certificates)  # pragma: no cover

            except (ImportError, AttributeError, TypeError) as exc:
                self.log(f"Error applying filter {filter_config['func']}: {exc}")
                continue

        return filtered_certificates

    def convert_certificates_to_service_format(self, certificates, service_config: dict) -> List[Dict]:
        """
        Convert certificates to the format required by the service.

        Processes each certificate according to the field configuration specified
        in the service config. Extracts configured fields and applies any
        transformations before building the final data structure.

        Args:
            certificates: Iterable of certificate objects to convert.
            service_config (dict): Service configuration containing:
                - fields (list, optional): List of field configurations for extraction

        Returns:
            List[Dict]: List of dictionaries containing certificate data formatted
                for the target service. Only certificates with successfully extracted
                data are included.
        """
        fields_config = service_config.get("fields", [])
        converted_data = []

        for certificate in certificates:
            cert_data = {}
            for field_config in fields_config:
                field_name = field_config["name"]
                field_value = self.extract_field_value(certificate, field_config)
                if field_value is not None:
                    cert_data[field_name] = field_value

            if cert_data:
                converted_data.append(cert_data)

        return converted_data

    def _validate_service_config(self, service_config: dict) -> None:
        """
        Validate service configuration parameters.

        Checks that the authentication type is supported and other required
        configuration parameters are present.

        Args:
            service_config (dict): Service configuration containing:
                - service_name (str, optional): Name of the service for error reporting
                - auth_type (str, optional): Authentication type, defaults to 'bearer'

        Raises:
            ValueError: If auth_type is not in VALID_AUTH_TYPES.
        """
        service_name = service_config.get("service_name")
        auth_type = service_config.get("auth_type", "bearer")

        if auth_type not in self.VALID_AUTH_TYPES:
            raise ValueError(
                f"Invalid auth_type '{auth_type}' for service '{service_name}'. "
                f"Valid options: {', '.join(self.VALID_AUTH_TYPES)}"
            )

    def _prepare_auth_headers(self, service_config: dict) -> dict:
        """
        Prepare authentication headers based on service configuration.

        Builds HTTP headers with appropriate authentication based on the configured
        authentication type. Supports Bearer tokens, Basic authentication, and API keys.

        Args:
            service_config (dict): Service configuration containing:
                - auth_token (str, optional): Authentication token
                - auth_type (str, optional): Authentication type, defaults to 'bearer'
                - auth_header (str, optional): Header name, defaults to 'Authorization'

        Returns:
            dict: Dictionary of HTTP headers including authentication if configured.
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        auth_token = service_config.get("auth_token")
        auth_type = service_config.get("auth_type", "bearer")
        auth_header = service_config.get("auth_header", "Authorization")

        if auth_token:
            if auth_type == "bearer":
                headers[auth_header] = f"Bearer {auth_token}"
            elif auth_type == "basic":
                credentials = base64.b64encode(auth_token.encode()).decode()
                headers[auth_header] = f"Basic {credentials}"
            elif auth_type == "api_key":
                headers[auth_header] = auth_token

        return headers

    def _log_dry_run_info(self, service_config: dict, certificates_data: List[Dict]) -> None:
        """
        Log dry run information.

        Outputs detailed information about what would be sent to the service
        during a dry run, including endpoint URL, authentication details, timeout, and payload.

        Args:
            service_config (dict): Service configuration containing:
                - endpoint_url (str): API endpoint URL
                - endpoint_timeout (int, optional): Request timeout in seconds
                - auth_token (str, optional): Authentication token
                - auth_type (str, optional): Authentication type
                - auth_header (str, optional): Authentication header name
            certificates_data (List[Dict]): The certificate data that would be sent.
        """
        api_url = service_config["endpoint_url"]
        timeout = service_config.get("endpoint_timeout", 60)
        auth_token = service_config.get("auth_token")
        auth_type = service_config.get("auth_type", "bearer")
        auth_header = service_config.get("auth_header", "Authorization")

        self.log(f"[DRY RUN] Would send to {api_url}")
        self.log(f"[DRY RUN] Headers would include: {auth_type} authentication")
        self.log(f"[DRY RUN] Auth header: {auth_header}")
        self.log(f"[DRY RUN] Auth token: {'Configured' if auth_token else 'Not configured'}")
        self.log(f"[DRY RUN] Request timeout: {timeout} seconds")
        self.log("[DRY RUN] Payload:")
        self.log(json.dumps(certificates_data, indent=2, ensure_ascii=False))

    def _send_http_request(self, api_url: str, headers: dict, certificates_data: List[Dict], timeout: int) -> bool:
        """
        Send HTTP request to external service.

        Performs the actual HTTP POST request to send certificate data to the
        external service. Handles timeout and error conditions.

        Args:
            api_url (str): The API endpoint URL.
            headers (dict): HTTP headers including authentication.
            certificates_data (List[Dict]): Certificate data to send.
            timeout (int): Request timeout in seconds.

        Returns:
            bool: True if the request was successful, False otherwise.
        """
        try:
            response = requests.post(
                api_url,
                json=certificates_data,
                headers=headers,
                timeout=timeout,
            )

            if response.ok:
                return True

            self.log(f"Failed to send certificates: {response.text}")
            return False

        except requests.RequestException as exc:
            self.log(f"Request error: {exc}")
            return False

    def send_certificates_to_service(self, service_config: dict, certificates_data: List[Dict], dry_run: bool) -> bool:
        """
        Send certificates to external service.

        Main method for sending certificate data to an external service. Handles
        dry run mode, authentication, and error reporting.

        Args:
            service_config (dict): Service configuration containing:
                - service_name (str): Name of the service
                - endpoint_url (str): API endpoint URL
                - endpoint_timeout (int, optional): Request timeout in seconds, defaults to 60
                - auth_type (str, optional): Authentication type
                - auth_token (str, optional): Authentication token
                - auth_header (str, optional): Authentication header name
            certificates_data (List[Dict]): Certificate data to send.
            dry_run (bool): If True, only logs what would be sent without making actual request.

        Returns:
            bool: True if successful (or dry run), False if sending failed.

        Raises:
            ValueError: If service configuration is invalid.
        """
        service_name = service_config["service_name"]
        api_url = service_config["endpoint_url"]
        timeout = service_config.get("endpoint_timeout", 60)

        self._validate_service_config(service_config)

        if dry_run:
            self._log_dry_run_info(service_config, certificates_data)
            return True

        self.log(f"Sending {len(certificates_data)} certificates to {service_name}")
        self.log(f"Data: {certificates_data}")

        headers = self._prepare_auth_headers(service_config)

        success = self._send_http_request(api_url, headers, certificates_data, timeout)

        if success:
            self.log(f"Certificates sent successfully to {service_name}")
        else:
            self.log(f"Failed to send certificates to {service_name}")

        return success

    def get_certificates_queryset(self, days: int, certificate_id: int | None) -> QuerySet:
        """
        Get certificates queryset filtered by date and optionally by certificate ID.

        Args:
            days (int): Number of days to look back from current date.
            certificate_id (int | None): Specific certificate ID to filter by.
                If provided, only this certificate will be returned regardless of date.

        Returns:
            QuerySet: Filtered and ordered certificates queryset with user relations.
        """
        if certificate_id:
            queryset = use_read_replica_if_available(
                GeneratedCertificate.objects.filter(id=certificate_id).select_related("user")
            )

            if not queryset.exists():
                self.log(f"WARNING: Certificate with ID {certificate_id} does not exist.")
                return GeneratedCertificate.objects.none()

            return queryset

        begin_date = datetime.now(UTC) - timedelta(days=days)
        return use_read_replica_if_available(
            GeneratedCertificate.objects.filter(created_date__gte=begin_date)
            .order_by("created_date")
            .select_related("user")
        )

    def _get_processing_parameters(self, service_config: dict, options: dict) -> dict:
        """
        Extract and validate processing parameters.

        Combines command-line options with service configuration defaults to determine
        processing parameters like days, page size, certificate ID, and dry run mode.

        Args:
            service_config (dict): Service configuration containing:
                - days (int, optional): Default number of days, defaults to 7
                - page_size (int, optional): Default page size, defaults to 1000
            options (dict): Command options containing:
                - days (int, optional): Override for days parameter
                - page_size (int, optional): Override for page size
                - certificate_id (int, optional): Specific certificate ID to process
                - dry_run (bool, optional): Dry run mode flag

        Returns:
            dict: Dictionary containing validated processing parameters:
                - days (int): Number of days to process
                - page_size (int): Page size for pagination
                - certificate_id (int, optional): Specific certificate ID
                - dry_run (bool): Dry run mode flag
        """
        days = options.get("days")
        if days is None:
            days = service_config.get("days", 7)

        page_size = options.get("page_size")
        if page_size is None:
            page_size = service_config.get("page_size", 1000)

        return {
            "days": days,
            "page_size": page_size,
            "certificate_id": options.get("certificate_id"),
            "dry_run": options.get("dry_run", False),
        }

    def _process_certificates_page(self, certificates, service_config: dict, dry_run: bool) -> bool:
        """
        Process a single page of certificates.

        Converts certificates to service format and sends them to the external service.
        Handles empty certificate lists gracefully.

        Args:
            certificates (QuerySet): Queryset of certificate objects to process.
            service_config (dict): Service configuration for conversion and sending.
            dry_run (bool): If True, only logs what would be sent.

        Returns:
            bool: True if processing was successful, False otherwise.
        """
        if not certificates:
            return True

        certificates_data = self.convert_certificates_to_service_format(certificates, service_config)

        if certificates_data:
            return self.send_certificates_to_service(service_config, certificates_data, dry_run)

        return True

    def _process_certificates_pages(self, certificates_queryset: QuerySet, service_config: dict, params: dict) -> None:
        """
        Process certificates in pages.

        Handles pagination of certificates and processes each page sequentially.
        Logs progress and handles failures gracefully by continuing to the next page.

        Args:
            certificates_queryset (QuerySet): Queryset of certificates to process.
            service_config (dict): Service configuration for processing.
            params (dict): Processing parameters containing:
                - page_size (int): Size of each page
                - dry_run (bool): Dry run mode flag
        """
        service_name = service_config.get("service_name")
        page_size = params["page_size"]
        dry_run = params["dry_run"]

        paginator = Paginator(certificates_queryset, page_size)
        total_count = paginator.count
        processed_count = 0

        self.log(f"Total certificates to process: {total_count}")

        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            certificates = page.object_list
            processed_count += len(certificates)

            self.log(f"Processing {processed_count} of {total_count} certificates (page {page_num})")

            success = self._process_certificates_page(certificates, service_config, dry_run)
            if not success:
                self.log(f"Failed to send page {page_num} to {service_name}")

    def process_service(self, service_config: dict, options: dict) -> None:
        """
        Process certificates for a specific service.

        This is the main entry point for the certificate processing business logic.
        Handles the complete workflow from parameter validation to certificate
        retrieval, filtering, and sending to external services.

        Args:
            service_config (dict): Complete service configuration containing:
                - service_name (str): Name of the service
                - endpoint_url (str): API endpoint URL
                - auth_type (str, optional): Authentication type
                - auth_token (str, optional): Authentication token
                - days (int, optional): Default number of days to process
                - page_size (int, optional): Default page size
                - filters (list, optional): List of filter configurations
                - fields (list, optional): List of field extraction configurations
            options (dict): Processing options containing:
                - days (int, optional): Override for days parameter
                - page_size (int, optional): Override for page size
                - certificate_id (int, optional): Specific certificate ID to process
                - dry_run (bool, optional): Dry run mode flag
        """
        service_name = service_config.get("service_name")
        self.log(f"\n=== Processing service: {service_name} ===")

        params = self._get_processing_parameters(service_config, options)

        if params["certificate_id"]:
            self.log(f"Processing specific certificate with ID: {params['certificate_id']}")
        else:
            self.log(f"Processing certificates from the last {params['days']} days")
            self.log(f"Page size: {params['page_size']}")

        certificates_queryset = self.get_certificates_queryset(params["days"], params["certificate_id"])
        certificates_queryset = self.apply_filters(certificates_queryset, service_config)

        self._process_certificates_pages(certificates_queryset, service_config, params)
