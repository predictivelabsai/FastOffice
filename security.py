"""Signing and encryption helpers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken


def _secret() -> bytes:
    raw = (
        os.getenv("FASTOFFICE_SSO_SECRET")
        or os.getenv("FASTOFFICE_SESSION_SECRET", "fastoffice-dev-secret-change-me")
    )
    return raw.encode()


def sign_ticket(payload: dict, ttl: int = 60) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl
    body["jti"] = secrets.token_urlsafe(16)
    encoded = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_ticket(token: str, audience: str) -> dict | None:
    try:
        encoded, supplied = token.split(".", 1)
        expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            return None
        body = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if body.get("exp", 0) < int(time.time()) or body.get("aud") != audience:
            return None
        return body
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _fernet() -> Fernet:
    configured = os.getenv("FASTOFFICE_ENCRYPTION_KEY", "").encode()
    key = configured or base64.urlsafe_b64encode(hashlib.sha256(_secret()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode() if value else ""
    except InvalidToken:
        return ""
