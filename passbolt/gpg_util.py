"""GPGAuth helpers that do not require python-gnupg."""

from __future__ import annotations

import uuid
from urllib.parse import unquote_plus


def normalize_fingerprint(fingerprint: str) -> str:
    """Return a clean uppercase fingerprint without spaces or hyphens."""
    return fingerprint.replace("-", "").replace(" ", "").upper()


def check_auth_token_format(auth_token: str) -> None:
    """Validate a decrypted GPGAuth token."""
    parts = auth_token.split("|")
    if len(parts) != 4:
        raise ValueError("Auth token has wrong number of fields")
    if parts[0] != parts[3]:
        raise ValueError("Auth token version fields do not match")
    if not parts[0].startswith("gpgauth"):
        raise ValueError("Auth token version does not start with 'gpgauth'")
    try:
        length = int(parts[1])
    except ValueError as exc:
        raise ValueError("Auth token length field is not an integer") from exc
    if len(parts[2]) != length:
        raise ValueError("Auth token data length does not match length field")


def decode_gpgauth_header_value(value: str) -> str:
    """Decode a GPGAuth header value from the HTTP response."""
    return unquote_plus(value.replace("\\+", "+"))


def make_gpgauth_token() -> str:
    """Create a GPGAuth verification token."""
    token_id = str(uuid.uuid4())
    return f"gpgauthv1.3.0|36|{token_id}|gpgauthv1.3.0"