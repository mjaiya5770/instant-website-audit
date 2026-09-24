"""Stateless report tokens.

Serverless deployments (Vercel) have no shared in-memory state across
invocations, so an audit's data/result can't live in a process dict.
Instead, /api/audit returns an HMAC-signed token that carries the compact
audit data + result. /buy and /report verify the signature instead of
looking anything up.

The token is tamper-proof but NOT encrypted: it contains the same signals
the free teaser already shows (titles, check statuses, scores). The fix
tips and PDF layout stay server-side in report.py.

Signing key: env var AUDIT_SIGNING_KEY. In production this MUST be set to
a stable random value (all instances share it). Locally, an ephemeral key
is generated per process (tokens only live as long as the dev server).
"""

import base64
import hashlib
import hmac
import json
import os
import secrets

_VERSION = "v1"
_key = None


def key():
    global _key
    if _key is None:
        _key = os.environ.get("AUDIT_SIGNING_KEY") or secrets.token_hex(32)
    return _key.encode("utf-8")


def key_is_stable():
    """True when AUDIT_SIGNING_KEY is set (production-safe)."""
    return bool(os.environ.get("AUDIT_SIGNING_KEY"))


def encode(data, result):
    """Sign (data, result) -> URL-safe token string."""
    payload = json.dumps(
        {"v": _VERSION, "data": data, "result": result},
        separators=(",", ":"),
    ).encode("utf-8")
    sig = hmac.new(key(), payload, hashlib.sha256).hexdigest()
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return body + "." + sig


def decode(token):
    """Verify token -> (data, result), or None if invalid/tampered."""
    try:
        body, sig = token.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        expected = hmac.new(key(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        obj = json.loads(payload.decode("utf-8"))
        if obj.get("v") != _VERSION:
            return None
        return obj["data"], obj["result"]
    except Exception:
        return None
