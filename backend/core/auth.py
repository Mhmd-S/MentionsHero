"""Supabase session authentication dependencies for FastAPI.

Tokens are verified locally against the project's JWKS. The previous version called
`supabase.auth.get_user(token)` on every single request, which meant a round-trip to
Supabase Auth before any endpoint could run — on every page load, every poll and
every SSE reconnect. That was the main source of the "everything is slow" symptom.

This project uses asymmetric ES256 signing keys, so the public key set at
  {SUPABASE_URL}/auth/v1/.well-known/jwks.json
is fetched once, cached in-process, and refreshed automatically when a token
arrives with an unknown `kid` (key rotation) or the cache lifespan expires.
Projects still on the legacy shared secret are handled too, via SUPABASE_JWT_SECRET.
"""

import logging
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError, PyJWTError

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.services import profile_service

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# Supabase issues user tokens with aud="authenticated".
_AUDIENCE = "authenticated"
_ASYMMETRIC_ALGORITHMS = ["ES256", "RS256"]

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired session",
)


def _issuer() -> str:
    return f"{get_settings().supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def _jwk_client() -> PyJWKClient:
    """Cached JWKS client. Built lazily so importing this module makes no network call."""
    url = f"{get_settings().supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(
        url,
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=600,  # matches Supabase's own edge cache window
        max_cached_keys=16,
        timeout=5,
    )


def _decode(token: str, key, algorithms: list[str]) -> dict:
    return jwt.decode(
        token,
        key,
        algorithms=algorithms,
        audience=_AUDIENCE,
        issuer=_issuer(),
        options={
            "require": ["exp", "sub", "aud", "iss"],
            "verify_exp": True,
            "verify_aud": True,
            "verify_iss": True,
        },
        leeway=10,  # tolerate small clock skew between us and Supabase
    )


def _validate_remotely(token: str) -> dict:
    """Last-resort verification via the Auth API.

    Only used when the JWKS endpoint itself is unreachable. It must never be a
    fallback for a token that failed signature or expiry checks — that would turn a
    rejected token into an accepted one.
    """
    try:
        response = get_supabase().auth.get_user(token)
    except Exception as exc:
        logger.warning("Remote token validation failed: %s", exc)
        raise _UNAUTHORIZED from exc

    if response and response.user:
        return {"sub": response.user.id, "email": response.user.email}
    raise _UNAUTHORIZED


def _validate_session(token: str) -> dict:
    """Verify an access token and return {'sub', 'email'}."""
    try:
        header = jwt.get_unverified_header(token)
    except PyJWTError as exc:
        logger.debug("Malformed token header: %s", exc)
        raise _UNAUTHORIZED from exc

    algorithm = header.get("alg")

    try:
        if algorithm == "HS256":
            # Legacy symmetric signing. Never accept HS256 against a JWKS public key:
            # that is the classic algorithm-confusion vulnerability.
            secret = get_settings().supabase_jwt_secret
            if not secret:
                logger.error(
                    "Received an HS256 token but SUPABASE_JWT_SECRET is not set; "
                    "falling back to the Auth API."
                )
                return _validate_remotely(token)
            claims = _decode(token, secret, ["HS256"])
        elif algorithm in _ASYMMETRIC_ALGORITHMS:
            signing_key = _jwk_client().get_signing_key_from_jwt(token)
            claims = _decode(token, signing_key.key, _ASYMMETRIC_ALGORITHMS)
        else:
            logger.warning("Rejecting token with unsupported alg %r", algorithm)
            raise _UNAUTHORIZED
    except PyJWKClientError as exc:
        # The key set could not be fetched — an availability problem on our side, not
        # a bad token. Fall back rather than signing everyone out.
        logger.warning("JWKS unavailable, falling back to remote validation: %s", exc)
        return _validate_remotely(token)
    except PyJWTError as exc:
        logger.debug("Token rejected: %s", exc)
        raise _UNAUTHORIZED from exc

    subject = claims.get("sub")
    if not subject:
        raise _UNAUTHORIZED

    return {"sub": subject, "email": claims.get("email")}


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Extract token from Authorization header or ?token query param."""
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.query_params.get("token")


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate session from Authorization header or ?token query param (for SSE)."""
    token = _extract_token(request, credentials)
    if token:
        return _validate_session(token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


async def require_user_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Require any authenticated user (admin or client)."""
    return await require_auth(request, credentials)


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Require an authenticated user whose profiles.role is 'admin'.

    The role is read from the database, never from the token: `user_metadata` is
    client-writable, so trusting a claim for authorisation would let any user
    promote themselves.
    """
    user = await require_auth(request, credentials)

    if profile_service.get_role(user["sub"]) == "admin":
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )
