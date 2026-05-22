"""Shared secret parsing utilities"""

from __future__ import annotations

import json
from typing import Any


def parse_secret(secret: str) -> dict[str, Any]:
    """Parse a Passbolt secret string into a dict.

    Passbolt secrets are JSON strings containing fields like
    'password', 'description', etc. Falls back to returning
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
