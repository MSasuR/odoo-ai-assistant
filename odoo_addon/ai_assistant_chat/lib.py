"""Signing of the assistant token. Standard library only (testable without Odoo).

Format identical to api/auth.py in the FastAPI service:
    base64url(payload_json) + "." + base64url(HMAC-SHA256(payload_b64, secret))
"""
import base64
import hashlib
import hmac
import json
import time


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign_token(payload: dict, secret: str, ttl: int = 300) -> str:
    body = _b64(json.dumps({**payload, "exp": int(time.time()) + ttl}, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"
