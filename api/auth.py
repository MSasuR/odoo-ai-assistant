"""HMAC-SHA256 signed token: issued by the Odoo module, verified by this API.

Format: base64url(payload_json) + "." + base64url(signature). The payload carries the
identity of the Odoo user (uid, employee id, allowed companies, groups) and a short
`exp`. The browser never sees the secret; only Odoo signs.
"""
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field

from api.config import settings


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class UserContext:
    uid: int
    employee_id: int | None
    company_ids: list[int] = field(default_factory=list)
    groups: frozenset[str] = frozenset()

    def in_any_group(self, required: set[str]) -> bool:
        return bool(self.groups & required)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(payload: dict, secret: str | None = None, ttl: int = 300) -> str:
    body = _b64(json.dumps({**payload, "exp": int(time.time()) + ttl}, separators=(",", ":")).encode())
    sig = hmac.new((secret or settings.hmac_secret).encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(sig)}"


def verify_token(token: str, secret: str | None = None) -> UserContext:
    try:
        body, sig = token.split(".")
        expected = hmac.new((secret or settings.hmac_secret).encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(sig)):
            raise AuthError("invalid signature")
        payload = json.loads(_unb64(body))
    except AuthError:
        raise
    except Exception as e:
        raise AuthError("malformed token") from e
    if payload.get("exp", 0) < time.time():
        raise AuthError("token expired")
    return UserContext(
        uid=payload["uid"],
        employee_id=payload.get("employee_id"),
        company_ids=list(payload.get("company_ids", [])),
        groups=frozenset(payload.get("groups", [])),
    )
