"""HTTP Basic Auth for the operator dashboard. Register/health stay open."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Optional

PROTECTED_PATHS = frozenset({"/", "/index.html", "/api/v1/overview"})
_LOCAL_BINDS = frozenset({"127.0.0.1", "localhost", "::1"})


def dashboard_username() -> str:
    return os.environ.get("NOVA_DASHBOARD_USER", "nova").strip() or "nova"


def dashboard_password() -> str:
    return os.environ.get("NOVA_DASHBOARD_PASSWORD", "").strip()


def dashboard_auth_required() -> bool:
    if dashboard_password():
        return True
    bind = os.environ.get("NOVA_BIND", "127.0.0.1").strip()
    return bind not in _LOCAL_BINDS


def is_protected_path(path: str) -> bool:
    return path in PROTECTED_PATHS


def authorization_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def credentials_match(authorization: Optional[str]) -> bool:
    expected_user = dashboard_username()
    expected_pass = dashboard_password()
    if not expected_pass:
        return False
    if not authorization:
        return False
    scheme, _, rest = authorization.partition(" ")
    if scheme.lower() != "basic" or not rest.strip():
        return False
    try:
        raw = base64.b64decode(rest.strip(), validate=True)
        decoded = raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    if ":" not in decoded:
        return False
    user, password = decoded.split(":", 1)
    user_ok = _same(user, expected_user)
    pass_ok = _same(password, expected_pass)
    return user_ok and pass_ok


def _same(left: str, right: str) -> bool:
    left_digest = hashlib.sha256(b"nova-dash\0" + left.encode("utf-8")).digest()
    right_digest = hashlib.sha256(b"nova-dash\0" + right.encode("utf-8")).digest()
    return hmac.compare_digest(left_digest, right_digest)
