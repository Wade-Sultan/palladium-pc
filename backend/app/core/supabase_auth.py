from __future__ import annotations

import logging
from uuid import UUID

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


# Supabase JWT claims

class SupabaseTokenPayload(BaseModel):
    sub: UUID = Field(..., description="auth.users UUID")
    email: str | None = None
    role: str = "authenticated"
    aud: str = "authenticated"

    # user_metadata from Supabase (sign-up metadata like full_name)
    user_metadata: dict | None = Field(default=None, alias="user_metadata")


# Verification

ALGORITHM = "HS256"


def _get_jwt_secret() -> str:
    """
    Return the Supabase JWT secret used to verify tokens.

    This is found in: Supabase Dashboard → Settings → API → JWT Secret.
    It must be set as SUPABASE_JWT_SECRET in your environment.
    Falls back to SECRET_KEY for local dev with self-issued tokens.
    """
    secret = getattr(settings, "SUPABASE_JWT_SECRET", None) or settings.SECRET_KEY
    if secret == settings.SECRET_KEY:
        logger.warning(
            "SUPABASE_JWT_SECRET not set — falling back to SECRET_KEY. "
            "This is fine for local dev but MUST be set in production."
        )
    return secret


def verify_supabase_token(token: str) -> SupabaseTokenPayload:
    """
    Decode and validate a Supabase JWT.

    Args:
        token: The raw Bearer token string from the Authorization header.

    Returns:
        SupabaseTokenPayload with the verified claims.

    Raises:
        InvalidTokenError: If the token is expired, tampered with, or
                           otherwise invalid.
    """
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[ALGORITHM],
            audience="authenticated",
            options={
                "require": ["sub", "exp", "aud"],
            },
        )
    except ExpiredSignatureError:
        logger.debug("Supabase JWT expired")
        raise
    except InvalidTokenError as exc:
        logger.debug("Supabase JWT invalid: %s", exc)
        raise

    return SupabaseTokenPayload(**payload)