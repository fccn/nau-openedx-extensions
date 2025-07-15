"""
Certificate engine.
"""

import base64
import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

import requests
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F, Func, OuterRef, Q, QuerySet, Subquery, Value
from django.db.models.functions import MD5, Concat, JSONObject
from django.utils.functional import cached_property
from pytz import UTC

from nau_openedx_extensions.coursecertificate.enums import FieldType, Transformations
from nau_openedx_extensions.coursecertificate.funcs import SubstringIndex, ToBase64
from nau_openedx_extensions.edxapp_wrapper.certificates import GeneratedCertificate
from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview
from nau_openedx_extensions.edxapp_wrapper.student import CourseEnrollment
from nau_openedx_extensions.edxapp_wrapper.util import use_read_replica_if_available

DatabaseExpression = Union[Func, F, Subquery, Concat]
CertificateData = Union[List[Dict[str, Any]], QuerySet]
ServiceConfig = Dict[str, Any]
CommandOptions = Dict[str, Any]


class CertificateFieldBuilder:
    """Handles building database expressions for certificate fields"""

    TRANSFORMATIONS = {
        Transformations.MD5.value: MD5,
        Transformations.BASE64.value: ToBase64,
    }

    @cached_property
    def subqueries(self) -> Dict[str, Subquery]:
        """Pre-built subqueries for common data"""
        return {
            "course_name": Subquery(
                CourseOverview.objects.filter(
                    id=OuterRef("course_id"),
                ).values("display_name")[:1],
            ),
            "enrolled_date": Subquery(
                CourseEnrollment.objects.filter(
                    user=OuterRef("user"),
                    course_id=OuterRef("course_id"),
                ).values("created")[:1],
            ),
        }

    @cached_property
    def substrings(self) -> Dict[str, DatabaseExpression]:
        """Pre-built substring expressions"""
        return {
            "course_number": SubstringIndex(
                SubstringIndex(F("course_id"), Value("+"), 2),
                Value("+"),
                -1,
            )
        }

    @cached_property
    def concatenated_fields(self) -> Dict[str, DatabaseExpression]:
        """Pre-built concatenated field expressions"""
        return {
            "certificate_url": Concat(
                Value(f"{settings.LMS_ROOT_URL}/certificates/"),
                F("verify_uuid"),
            ),
        }

    def build_field_expression(self, field_config: Dict[str, Any]) -> DatabaseExpression:
        """Build database expression for a field configuration"""
        field_type = field_config.get("type")
        if not field_type:
            raise ValueError("Field configuration must specify a 'type'")

        # Build base expression
        expr = self._build_base_expression(field_config, field_type)

        transformation = field_config.get("trans")
        if transformation and transformation in self.TRANSFORMATIONS:
            expr = self.TRANSFORMATIONS[transformation](expr)

        return expr

    def _build_base_expression(self, field_config: Dict[str, Any], field_type: str) -> DatabaseExpression:
        """Build the base expression based on field type"""
        if field_type == FieldType.STANDARD.value:
            return F(field_config["model_field"])

        elif field_type == FieldType.CONCATENATED.value:
            concat_key = field_config["concat"]
            return self.concatenated_fields[concat_key]

        elif field_type == FieldType.COMPUTED.value:
            subquery_name = field_config["subquery"]
            return self.subqueries[subquery_name]

        elif field_type == FieldType.SUBSTRING.value:
            substring_key = field_config["substring"]
            return self.substrings[substring_key]

        else:
            raise ValueError(f"Invalid field type: {field_type}")


class CertificateFilter:
    """Handles filtering of certificates based on service configuration"""

    FILTERS = {
        "certificate_by_course_id_regex": lambda regex: Q(course_id__regex=regex),
        "certificate_by_org": lambda org: Q(course_id__regex=rf"^course-v1:{org}\+"),
    }

    def apply_filters(self, certificates: QuerySet, service_config: ServiceConfig) -> QuerySet:
        """Apply all configured filters to the certificates queryset"""
        filters = service_config.get("filters", [])

        for filter_config in filters:
            filter_name = filter_config["name"]
            filter_args = filter_config.get("args")

            if filter_name not in self.FILTERS:
                raise ValueError(f"Unknown filter: {filter_name}")

            filter_func = self.FILTERS[filter_name]
            filter_expr = filter_func(filter_args)
            certificates = certificates.filter(filter_expr)

        return certificates


class ExternalServiceClient:
    """Handles communication with external services"""

    VALID_AUTH_TYPES = ["bearer", "basic", "api_key"]

    def __init__(self, logger: Callable[[str], None]):
        self.log = logger

    def send_data(self, service_config: ServiceConfig, data: CertificateData, dry_run: bool = False) -> bool:
        """Send certificate data to external service"""
        if dry_run:
            return self._log_dry_run(service_config, data)
        return self._send_request(service_config, data)

    def _log_dry_run(self, service_config: ServiceConfig, data: CertificateData) -> bool:
        """Log what would be sent in dry run mode"""
        api_url = service_config["endpoint_url"]
        auth_type = service_config.get("auth_type", "bearer")
        auth_header = service_config.get("auth_header", "Authorization")
        auth_token = service_config.get("auth_token")

        self.log(f"[DRY RUN] Would send to {api_url}")
        self.log(f"[DRY RUN] Headers would include: {auth_type} authentication")
        self.log(f"[DRY RUN] Auth header: {auth_header}")
        self.log(f"[DRY RUN] Auth token: {'Configured' if auth_token else 'Not configured'}")
        self.log("[DRY RUN] Payload:")
        self.log(json.dumps(data, indent=2, ensure_ascii=False))
        return True

    def _send_request(self, service_config: ServiceConfig, data: CertificateData) -> bool:
        """Send actual HTTP request to external service"""
        service_name = service_config["service_name"]
        api_url = service_config["endpoint_url"]
        timeout = service_config["endpoint_timeout"]

        self.log(f"Sending {len(data)} certificates to {service_name}")

        try:
            headers = self._build_headers(service_config)
            response = requests.post(
                api_url,
                json=data,
                headers=headers,
                timeout=timeout,
            )

            if response.ok:
                self.log(f"Certificates sent successfully to {service_name}")
                return True

            self.log(f"Failed to send certificates to {service_name}: {response.text}")
            return False

        except requests.RequestException as exc:
            self.log(f"Request error sending to {service_name}: {exc}")
            return False

    def _build_headers(self, service_config: ServiceConfig) -> Dict[str, str]:
        """Build HTTP headers including authentication"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        auth_token = service_config.get("auth_token")
        if not auth_token:
            return headers

        auth_type = service_config.get("auth_type", "bearer")
        auth_header = service_config.get("auth_header", "Authorization")

        if auth_type not in self.VALID_AUTH_TYPES:
            service_name = service_config["service_name"]
            raise ValueError(
                f"Invalid auth_type '{auth_type}' for service '{service_name}'. "
                f"Valid options: {', '.join(self.VALID_AUTH_TYPES)}"
            )

        if auth_type == "bearer":
            headers[auth_header] = f"Bearer {auth_token}"
        elif auth_type == "basic":
            credentials = base64.b64encode(auth_token.encode()).decode()
            headers[auth_header] = f"Basic {credentials}"
        elif auth_type == "api_key":
            headers[auth_header] = auth_token

        return headers


class CertificateEngine:
    """
    Certificate processing engine - handles all business logic.
    Independent of Django commands and Celery tasks.
    """

    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        """
        Initialize the engine with an optional logger function.

        Args:
            logger: Function to log messages (defaults to print)
        """
        self.log = logger or print
        self.field_builder = CertificateFieldBuilder()
        self.certificate_filter = CertificateFilter()
        self.service_client = ExternalServiceClient(self.log)

    def process_service(self, service_config: ServiceConfig, options: CommandOptions) -> None:
        """
        Process certificates for a specific service.
        This is the main entry point for the business logic.
        """
        service_name = service_config.get("service_name")
        self.log(f"\n=== Processing service: {service_name} ===")

        days = options.get("days") or service_config.get("days", 7)
        page_size = options.get("page_size") or service_config.get("page_size", 1000)
        dry_run = options.get("dry_run", False)

        self.log(f"Processing certificates from the last {days} days")
        self.log(f"Page size: {page_size}")

        certificates_queryset = self._get_certificates_queryset(service_config, days)
        certificates_queryset = self.certificate_filter.apply_filters(certificates_queryset, service_config)

        self._process_certificates_in_batches(certificates_queryset, service_config, page_size, dry_run)

    def _get_certificates_queryset(self, service_config: ServiceConfig, days: int) -> QuerySet:
        """Build and return the certificates queryset with all annotations"""
        field_configs = service_config.get("fields", [])
        begin_date = datetime.now(UTC) - timedelta(days=days)

        # Build annotations and JSON structure
        annotations, json_fields = self._build_annotations(field_configs)

        # Add final JSON structure
        annotations["data"] = JSONObject(**json_fields)

        return use_read_replica_if_available(
            GeneratedCertificate.objects.filter(created_date__gt=begin_date)
            .annotate(**annotations)
            .order_by("created_date")
            .select_related("user")
            .values_list("data", flat=True)
        )

    def _build_annotations(self, field_configs: List[Dict[str, Any]]) -> tuple[Dict[str, Any], Dict[str, F]]:
        """Build database annotations and JSON field mappings"""
        annotations = {}
        json_fields = {}

        for field_config in field_configs:
            field_name = field_config["name"]

            # Build expression for this field
            expr = self.field_builder.build_field_expression(field_config)

            # Use internal annotation alias to avoid conflicts
            annotation_alias = f"annotated__{field_name}"
            annotations[annotation_alias] = expr
            json_fields[field_name] = F(annotation_alias)

        return annotations, json_fields

    def _process_certificates_in_batches(
        self, certificates_queryset: QuerySet, service_config: ServiceConfig, page_size: int, dry_run: bool
    ) -> None:
        """Process certificates in paginated batches"""
        service_name = service_config.get("service_name")

        certificates_list = list(certificates_queryset)
        paginator = Paginator(certificates_list, page_size)

        total_count = paginator.count
        processed_count = 0

        self.log(f"Total certificates to process: {total_count}")

        if total_count == 0:
            self.log("No certificates to process")
            return

        for page_num in paginator.page_range:
            page = paginator.page(page_num)
            certificates = page.object_list
            processed_count += len(certificates)

            self.log(
                f"Processing batch {page_num}/{paginator.num_pages} ({processed_count}/{total_count} certificates)"
            )

            success = self.service_client.send_data(service_config, certificates, dry_run)

            if not success:
                self.log(f"Failed to send batch {page_num} to {service_name}")
