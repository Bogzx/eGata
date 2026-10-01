"""JWT minting + verification."""
from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError

from app.config import get_settings

JWT_ISSUER = "egata"

_bearer = HTTPBearer(auto_error=False)


def mint_access_token(citizen_id: UUID | str) -> str:
    settings = get_settings()
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(citizen_id),
        "iat": now,
        "exp": now + settings.jwt_expires_seconds,
        "iss": JWT_ISSUER,
    }
    return jwt.encode(payload, settings.jwt_signing_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode + verify a JWT. Distinguishes "expired" from generic "invalid".

    The frontend branches on `detail`: an expired token triggers a silent
    re-login redirect; an invalid token (signature mismatch, malformed,
    tampered) is a real error worth surfacing. Pre-fix both raised the
    same `Invalid token` detail and the chat appeared broken whenever a
    long-idle session crossed the 24h JWT lifetime.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_signing_secret,
            algorithms=[settings.jwt_algorithm],
            # Every token this app has minted carries iss="egata"; checking it
            # keeps a token signed with the same secret for another purpose
            # from passing as a login.
            issuer=JWT_ISSUER,
            options={"require": ["exp", "sub", "iss"]},
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    return payload


def current_citizen_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UUID:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    payload = decode_token(creds.credentials)
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid subject")
    try:
        return UUID(sub)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid subject") from exc
