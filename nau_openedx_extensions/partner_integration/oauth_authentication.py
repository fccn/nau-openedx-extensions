"""Implementation of OAuth authentication for PartnerAPIClient using JWT."""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from rest_framework import exceptions
from rest_framework.permissions import BasePermission

from .models import PartnerAPIClient

logger = logging.getLogger(__name__)


class IsAuthenticatedPartnerAPIClient(BasePermission):
    """
    Allows access only to authenticated `PartnerAPIClient`s.
    """

    def has_permission(self, request, view):
        return bool(request.partner_client and request.partner_client.is_authenticated)


class ClientJWTAuthentication(JwtAuthentication):
    """
    JWT authentication for PartnerAPIClient.
    """

    def authenticate(self, request):
        """
        Authenticate a client using JWT from Authorization header or cookies.
        """
        raw_token = self.get_token_from_request(request)
        if raw_token is None:
            raise exceptions.AuthenticationFailed("Missing token")

        token_data = self.get_validated_token(raw_token)
        client_id = token_data.get("user_id")

        try:
            client = PartnerAPIClient.objects.get(id=client_id, is_active=True)
        except PartnerAPIClient.DoesNotExist as e:
            logger.error("ClientJWTAuthentication: Invalid client ID provided in token.")
            raise exceptions.AuthenticationFailed("Invalid client") from e

        request.partner_client = client

        return (AnonymousUser(), raw_token)

    @classmethod
    def get_validated_token(cls, raw_token):
        """
        Decode JWT and validate using Open edX configured handler.
        """
        try:
            payload = cls.jwt_decode_token(raw_token)
        except Exception as e:
            logger.error("ClientJWTAuthentication: Invalid token provided.")
            raise exceptions.AuthenticationFailed(f"Invalid token: {e}")

        return payload

    @classmethod
    def get_token_from_request(cls, request):
        """
        Return JWT from Authorization header or cookies.
        """
        token = request.headers.get("Authorization")
        if token:
            parts = token.split()
            if len(parts) == 2 and parts[0] == "Bearer":
                return parts[1]

        return None

    @classmethod
    def issue_client_jwt(cls, client):
        """
        Issue a JWT for PartnerAPIClient that is fully compatible with Open edX `JwtAuthentication`.
        """
        expiration_seconds = getattr(settings, "JWT_PARTNER_CLIENT_EXPIRATION", 7200)
        now = timezone.now()
        payload = {
            "user_id": str(client.id),
            "username": client.username,
            "exp": now + timedelta(seconds=expiration_seconds),
            "iat": now,
            "iss": settings.JWT_AUTH.get("JWT_ISSUER"),
            "aud": settings.JWT_AUTH.get("JWT_AUDIENCE"),
        }

        token = cls.jwt_encode_payload(payload)
        return token
