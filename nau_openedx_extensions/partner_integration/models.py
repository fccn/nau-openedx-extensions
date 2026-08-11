"""Models for Partner API Client and related functionality."""

import logging
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from nau_openedx_extensions.edxapp_wrapper.certificates import GeneratedCertificate
from nau_openedx_extensions.edxapp_wrapper.content import CourseOverview

logger = logging.getLogger(__name__)


class PartnerAPIClientManager(BaseUserManager):
    """Manager for PartnerAPIClient, handling user and superuser creation."""

    def create_user(self, name, **extra_fields):
        """
        Create and save a standard PartnerAPIClient.
        """
        if not name:
            raise ValueError("The Name must be set")
        client = self.model(name=name, **extra_fields)
        client.save(using=self._db)
        return client

    def create_superuser(self, name, **extra_fields):
        """
        Create and save a superuser PartnerAPIClient.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(name, **extra_fields)


class PartnerAPIClient(AbstractBaseUser, PermissionsMixin):
    """
    Can authenticate via JWT and works with DRF and templates.
    """
    name = models.CharField(max_length=100, unique=True)
    client_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    password = models.CharField(max_length=128)
    query_security_scope = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='partner_clients',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='partner_client_permissions',
        blank=True,
    )

    objects = PartnerAPIClientManager()

    USERNAME_FIELD = 'name'
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        """
        Override save to validate basis for new PartnerAPIClient instances.
        """
        self.validate_basis(self.query_security_scope)
        super().save(*args, **kwargs)

    def check_password(self, password):
        """
        Override check_password in order to have a different behavior.
        """
        return password == self.password

    @property
    def email(self):
        """
        Compatibility property for Django code expecting an email attribute.
        """
        return f"{self.client_id}@example.com"

    @property
    def username(self):
        """
        Compatibility property for Django code expecting a username attribute.
        """
        return self.name

    @property
    def profile(self):
        """
        Dummy profile property for template and view compatibility.
        """
        class DummyProfile:
            has_profile_image = False

        return DummyProfile()

    def __str__(self):
        """String representation of the PartnerAPIClient."""
        return f"{self.name} - {self.client_id}"

    class Meta:
        app_label = "nau_openedx_extensions"

    def validate_basis(self, query_security_scope):
        """
        Validates the basic requirements for the facade to operate by checking
        the provided security and certificates scopes.

        This method performs the following checks:

        1. Ensures that the `base_security_scope` is not empty and contains at least
        one key starting with 'org'.
        2. For each field in the security and certificate scopes:
            - Validates that the field exists in the corresponding Django model.
            - Validates lookups for related fields (supports double underscore syntax).
            - Ensures that the field value is not None.
        3. Invalid fields or values are removed from the scope, and warnings/errors
        are logged for traceability.

        Parameters:
            `base_security_scope` (dict): A dictionary mapping field names to values
                for security-related validation against the CourseOverview model.
            `base_certificates_scope` (dict): A dictionary mapping field names to values
                for certificate-related validation against the GeneratedCertificate model.

        Notes:
            - The method modifies the input dictionaries in place by removing invalid entries.
            - Logging is performed for all removed or invalid fields.
            - Designed to fail-soft: invalid fields do not stop execution.
        """
        logger.info("Validating base security scope.")
        base_security_scope = query_security_scope.get("base_security_scope")
        base_certificates_scope = query_security_scope.get("base_certificates_scope")

        assert base_security_scope, "An integration must to have a query security scope defined. None found."
        has_org = any(str(key).startswith("org") for key in base_security_scope)
        assert has_org, (
            "Org field is the base of the query security scope, it must be provided. None found."
        )

        def is_valid_lookup(model, field_name, lookup):
            try:
                field = model._meta.get_field(field_name)
                if field.related_model:
                    return check_field(lookup, field.related_model)

                return field.get_lookup(lookup) is not None
            except BaseException as e:
                logger.error(f"Field lookup validation error for {field_name}__{lookup}: {e}")
                return False

        def check_field(field, model):
            valid_fields = [f.name for f in model._meta.get_fields()]
            field_name = str(field).split("__")
            if "__" in str(field):
                lookup_is_valid = is_valid_lookup(model, field_name[0], "__".join(field_name[1:]))
                if not lookup_is_valid:
                    logger.error(f"Invalid lookup for field {field}, it will be ignored.")
                    raise ValueError(f"Field {field} is invalid, it will be ignored.")
            elif field not in valid_fields:
                logger.error(f"Invalid field {field}, it will be ignored.")
                raise ValueError(f"Field {field} is invalid, it will be ignored.")

            return True

        def check_value(field, value):
            if value is None:
                logger.error(f"Field {field} has None value, it will be ignored.")
                raise ValueError(f"Field {field} has None value, it will be ignored.")

        for scope, model in [
            (base_security_scope, CourseOverview),
            (base_certificates_scope, GeneratedCertificate)
        ]:
            if scope:
                for field in list(scope.keys()):
                    value = scope.get(field)
                    try:
                        check_field(field, model)
                        check_value(field, value)
                    except BaseException as e:
                        logger.error(f"Removing invalid field {field} from scope: {e}")
                        del scope[field]


User = get_user_model()


class SSOPartnerIntegration(models.Model):
    """This model registers the users with completed SSO process

    A user may hold one link per partner client, so the relation to `User` is a
    plain foreign key. Both uniqueness rules are enforced by the database: a user
    is linked at most once per partner client, and an `external_user_id` belongs
    to a single NAU user within a partner client. The views rely on these
    constraints rather than on a preceding read, because a read cannot rule out a
    concurrent request claiming the same identifier.
    """
    partner_client = models.ForeignKey(PartnerAPIClient, on_delete=models.CASCADE, null=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    external_user_id = models.CharField(max_length=128, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "nau_openedx_extensions"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "partner_client"],
                name="unique_sso_link_per_user_and_partner_client",
            ),
            models.UniqueConstraint(
                fields=["partner_client", "external_user_id"],
                name="unique_sso_link_per_partner_client_and_external_user",
            ),
        ]

    def __str__(self):
        """String representation of the SSOPartnerIntegration."""
        return f"{self.partner_client.name} - {self.user.username} ({self.external_user_id})"
