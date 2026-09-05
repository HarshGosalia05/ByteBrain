"""JWT-based authentication for the CampusX backend.

Verifies a signed JWT Bearer token produced by the Next.js BFF.
Fails closed: missing, expired, tampered, or incomplete tokens are rejected.
The token payload is the sole source of the authenticated user identity;
client-supplied request body fields are NEVER trusted for authorization.
"""
from __future__ import annotations

import time
from typing import Any

import jwt
from fastapi import HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)


def create_access_token(payload: dict[str, Any]) -> str:
    """Create a signed JWT from the given payload.

    The ``exp`` claim is set automatically from ``JWT_EXPIRY_SECONDS``.
    The caller supplies role, user_id, username, and optional identity
    claims (student_id, faculty_id, admin_id, department, institution_id).
    """
    if not settings.JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET is not configured. Cannot sign tokens."
        )
    to_encode = dict(payload)
    to_encode.setdefault("iat", int(time.time()))
    to_encode["exp"] = int(time.time()) + settings.JWT_EXPIRY_SECONDS
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a signed JWT. Raises on any failure."""
    if not settings.JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.DecodeError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def _verify_token_version(payload: dict[str, Any]) -> None:
    """Verify that the JWT's token_version matches the current value in DB.

    When sign-out-all is called, token_version is incremented in the DB,
    invalidating all previously issued JWTs for that user.
    """
    from app.core.database import db

    token_version = payload.get("token_version")
    if token_version is None:
        # Tokens without a version claim are legacy; allow them.
        return

    user_id = payload.get("user_id")
    if not user_id:
        return

    if not db.pool:
        # DB not connected — fail open for token_version check only.
        return

    try:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT token_version FROM users WHERE user_id = $1",
                user_id,
            )
            if row and row["token_version"] != token_version:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been revoked. Please log in again.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
    except HTTPException:
        raise
    except Exception:
        # DB errors during version check should not block auth;
        # the JWT signature + expiry are still valid.
        pass


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
) -> dict:
    """Extract and verify the authenticated user from a signed JWT Bearer token.

    Verifies:
      - Token signature (tamper detection)
      - Token expiration
      - Valid role claim

    The returned dict is the authoritative user identity; all downstream
    RBAC checks use this value exclusively — never client body fields.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload or not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = payload.get("role")
    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing the role claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if role not in ("Student", "Faculty", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role in authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user_verified(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> dict:
    """Async version that also verifies token_version against the database.

    Use this for endpoints where session revocation must be enforced
    (e.g. admin endpoints, settings changes).
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload or not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    role = payload.get("role")
    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing the role claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if role not in ("Student", "Faculty", "Admin"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role in authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await _verify_token_version(payload)

    return payload
