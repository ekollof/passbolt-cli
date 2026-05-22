"""Shared secret parsing and TOTP generation utilities"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import struct
import time
from typing import Any

# Passbolt resource type IDs that contain TOTP data
TOTP_RESOURCE_TYPE_IDS = frozenset(
    {
        "05ba5c75-504d-5ad6-819a-83af68867d86",  # v4 standalone TOTP
        "8cca88d9-a3f6-56df-b860-3ef08de5c5c4",  # v4 password+description+TOTP
        "bb2280b5-c4d9-569c-9337-62b307f1139c",  # v5 standalone TOTP
        "7438294d-f71c-5164-b95-d9e60e295564",  # v5 default+TOTP
    }
)


def parse_secret(secret: str) -> dict[str, Any]:
    """Parse a Passbolt secret string into a dict.

    Passbolt secrets are JSON strings containing fields like
    'password', 'description', 'totp', etc. Falls back to returning
    ``{'password': secret}`` if the string is not valid JSON.

    This replaces the unsafe ``eval()`` pattern previously used.
    """
    try:
        data = json.loads(secret)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return {"password": secret}


def get_password_field(secret: str) -> str:
    """Extract the password field from a Passbolt secret string.

    Returns the raw secret if no 'password' key is found.
    """
    return parse_secret(secret).get("password", secret)


def has_totp(resource: dict[str, Any]) -> bool:
    """Check if a Passbolt resource has TOTP data based on its resource_type_id."""
    return resource.get("resource_type_id", "") in TOTP_RESOURCE_TYPE_IDS


def extract_totp(secret: str) -> dict[str, Any] | None:
    """Extract TOTP parameters from a decrypted secret string.

    Returns a dict with keys: secret_key, algorithm, digits, period.
    Returns None if no TOTP data is found.
    """
    data = parse_secret(secret)
    totp = data.get("totp")
    if not isinstance(totp, dict) or "secret_key" not in totp:
        return None
    return {
        "secret_key": totp["secret_key"],
        "algorithm": totp.get("algorithm", "SHA1"),
        "digits": totp.get("digits", 6),
        "period": totp.get("period", 30),
    }


def generate_totp(
    secret_key: str,
    algorithm: str = "SHA1",
    digits: int = 6,
    period: int = 30,
    timestamp: float | None = None,
) -> str:
    """Generate a TOTP code per RFC 6238.

    Args:
        secret_key: Base32-encoded secret key.
        algorithm: HMAC algorithm (SHA1, SHA256, SHA512).
        digits: Number of digits in the code (6 or 8).
        period: Time step in seconds (default 30).
        timestamp: Unix timestamp (defaults to now).

    Returns:
        The TOTP code as a zero-padded string.
    """
    if timestamp is None:
        timestamp = time.time()

    # Decode the base32 secret key
    key = base64.b32decode(secret_key, casefold=True)

    # Calculate time counter
    counter = int(timestamp) // period

    # Select hash algorithm
    hash_algo = {
        "SHA1": hashlib.sha1,
        "SHA256": hashlib.sha256,
        "SHA512": hashlib.sha512,
    }.get(algorithm.upper(), hashlib.sha1)

    # HOTP algorithm: HMAC-SHA(counter) → dynamic truncation
    counter_bytes = struct.pack(">Q", counter)
    hmac_result = hmac.new(key, counter_bytes, hash_algo).digest()

    # Dynamic truncation
    offset = hmac_result[-1] & 0x0F
    code = struct.unpack(">I", hmac_result[offset : offset + 4])[0]
    code &= 0x7FFFFFFF
    code %= 10**digits

    return str(code).zfill(digits)


def get_totp_for_resource(secret: str) -> str | None:
    """Generate a TOTP code for a resource's decrypted secret.

    Returns the TOTP code string, or None if the resource has no TOTP data.
    """
    totp_params = extract_totp(secret)
    if totp_params is None:
        return None
    return generate_totp(
        secret_key=totp_params["secret_key"],
        algorithm=totp_params["algorithm"],
        digits=totp_params["digits"],
        period=totp_params["period"],
    )
