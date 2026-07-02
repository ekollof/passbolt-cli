"""Helpers for Passbolt API response envelopes."""

from __future__ import annotations

from typing import Any


class APIError(Exception):
    """Raised when the Passbolt API returns an error envelope."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        body: Any = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.body = body
        detail = message
        if url:
            detail = f"{detail} ({url})"
        super().__init__(detail)


class MFARequiredError(APIError):
    """Raised when MFA verification is required before continuing."""


def extract_header(data: Any) -> dict[str, Any] | None:
    """Return the API header dict when present."""
    if isinstance(data, dict) and isinstance(data.get("header"), dict):
        return data["header"]
    return None


def extract_body(data: Any) -> Any:
    """Return the API body, falling back to the raw payload."""
    if isinstance(data, dict) and "body" in data:
        return data["body"]
    return data


def parse_envelope(data: Any) -> tuple[Any, dict[str, Any] | None]:
    """Split a Passbolt response into body and header."""
    return extract_body(data), extract_header(data)


def pagination_info(header: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return pagination metadata from a response header."""
    if not header:
        return None
    pagination = header.get("pagination")
    return pagination if isinstance(pagination, dict) else None


def is_mfa_challenge(header: dict[str, Any] | None) -> bool:
    """Return True when the response indicates MFA is required."""
    if not header:
        return False
    url = str(header.get("url", ""))
    return header.get("code") == 403 and url.endswith("/mfa/verify/error.json")


def ensure_success(data: Any) -> Any:
    """Validate a Passbolt envelope and return its body."""
    header = extract_header(data)
    if header is None:
        return extract_body(data)

    status = header.get("status")
    if status == "success":
        return extract_body(data)

    raise APIError(
        str(header.get("message", "API request failed")),
        status_code=header.get("code"),
        url=str(header.get("url", "")),
        body=extract_body(data),
    )