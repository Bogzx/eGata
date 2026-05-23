"""decode_token must distinguish expired tokens from generic invalid ones.

Pre-fix, both raised `Invalid token`, so the frontend couldn't decide
whether to silently re-login (expired) or surface a real error (tampered
/ malformed). The chat appeared broken whenever a session crossed the
24h JWT lifetime.
"""
from __future__ import annotations

import time

import pytest
from fastapi import HTTPException
from jose import jwt

from app.config import get_settings
from app.security import decode_token, mint_access_token


def test_valid_token_decodes():
    token = mint_access_token("11111111-1111-1111-1111-111111111111")
    payload = decode_token(token)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"


def test_expired_token_raises_token_expired_detail():
    settings = get_settings()
    # Mint a token that expired one second ago.
    now = int(time.time())
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "iat": now - 100,
        "exp": now - 1,
        "iss": "civicai",
    }
    expired = jwt.encode(
        payload, settings.jwt_signing_secret, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(HTTPException) as excinfo:
        decode_token(expired)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Token expired"


def test_invalid_signature_raises_invalid_token_detail():
    settings = get_settings()
    # Sign with a different secret so the signature check fails but the
    # token isn't expired.
    now = int(time.time())
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "iat": now,
        "exp": now + 3600,
        "iss": "civicai",
    }
    tampered = jwt.encode(
        payload, "wrong-secret", algorithm=settings.jwt_algorithm
    )
    with pytest.raises(HTTPException) as excinfo:
        decode_token(tampered)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Invalid token"


def test_malformed_token_raises_invalid_token_detail():
    with pytest.raises(HTTPException) as excinfo:
        decode_token("not-a-jwt-at-all")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Invalid token"
