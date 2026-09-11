"""Google ID token verification.

Provides an abstraction layer for verifying Google ID tokens server-side.
Uses the google-auth library for cryptographic verification.

Verification checks:
- Signature validity
- Issuer (accounts.google.com or securetoken.google.com)
- Audience (our Google Client ID)
- Expiration
- Subject (sub claim)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GoogleUserInfo:
    """Verified Google user information extracted from a valid ID token.

    All fields are extracted from the cryptographically verified token,
    NOT from untrusted request parameters.
    """

    sub: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None
    locale: str | None


class GoogleTokenVerifierProtocol(Protocol):
    """Protocol for Google token verification.

    This abstraction allows mocking in tests without calling Google's
    external service.
    """

    def verify(self, token: str) -> GoogleUserInfo:
        """Verify a Google ID token and return user information.

        Args:
            token: The Google ID token (credential) to verify.

        Returns:
            Verified user information.

        Raises:
            GoogleTokenError: If token verification fails.
        """
        ...


class GoogleTokenError(Exception):
    """Raised when Google token verification fails."""

    def __init__(self, message: str = "Invalid authentication credential") -> None:
        """Initialize with a safe error message.

        Args:
            message: Safe client-facing error message (no secrets).
        """
        super().__init__(message)
        self.message = message


class GoogleTokenVerifier:
    """Production implementation of Google ID token verification.

    Uses the google-auth library to cryptographically verify Google ID tokens.
    Verifies: signature, issuer, audience, expiration, and subject.
    """

    def __init__(
        self,
        client_id: str | None = None,
        allowed_issuers: list[str] | None = None,
    ) -> None:
        """Initialize the verifier.

        Args:
            client_id: Google Client ID for audience validation.
                Defaults to settings.GOOGLE_CLIENT_ID.
            allowed_issuers: Allowed token issuers.
                Defaults to settings.GOOGLE_ALLOWED_ISSUERS.
        """
        self._client_id = client_id or settings.GOOGLE_CLIENT_ID
        self._allowed_issuers = allowed_issuers or settings.GOOGLE_ALLOWED_ISSUERS

    def verify(self, token: str) -> GoogleUserInfo:
        """Verify a Google ID token and extract user information.

        Performs full cryptographic verification:
        1. Signature verification via Google's public keys
        2. Issuer validation
        3. Audience (client ID) validation
        4. Expiration check
        5. Subject extraction

        Args:
            token: The Google ID token credential.

        Returns:
            Verified user information.

        Raises:
            GoogleTokenError: If any verification step fails.
        """
        if not token or not token.strip():
            raise GoogleTokenError("Missing authentication credential")

        try:
            # Verify the token cryptographically
            # This checks: signature, issuer, audience, expiration
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=self._client_id,
            )  # type: ignore[no-untyped-call]

            # Extract and validate the subject
            sub = id_info.get("sub")
            if not sub:
                logger.warning("Google token is missing the subject identifier")
                raise GoogleTokenError()

            # Extract verified email
            email = id_info.get("email", "")
            email_verified = id_info.get("email_verified", False)

            # Extract optional profile data from verified token
            user_info = GoogleUserInfo(
                sub=sub,
                email=email,
                email_verified=bool(email_verified),
                name=id_info.get("name"),
                picture=id_info.get("picture"),
                locale=id_info.get("locale"),
            )

            logger.info(
                "Google token verified successfully",
                extra={"subject_prefix": sub[:8] + "***"},
            )

            return user_info

        except ValueError as exc:
            # google-auth raises ValueError for invalid tokens
            logger.warning(
                "Google token verification failed",
                extra={"error_type": type(exc).__name__},
                # Never log the actual error details or token
            )
            raise GoogleTokenError("Invalid authentication credential") from exc
        except GoogleTokenError:
            raise
        except Exception as exc:
            # Catch-all for unexpected errors — never leak details
            logger.error(
                "Unexpected error during Google token verification",
                extra={"error_type": type(exc).__name__},
            )
            raise GoogleTokenError("Authentication service unavailable") from exc


def get_google_verifier() -> GoogleTokenVerifier:
    """Factory function for the default Google token verifier.

    Returns:
        Configured GoogleTokenVerifier instance.
    """
    return GoogleTokenVerifier()
