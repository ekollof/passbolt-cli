"""Authenticated HTTP transport for the Passbolt API."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urljoin

import requests

from passbolt.api_response import (
    APIError,
    MFARequiredError,
    ensure_success,
    extract_header,
    is_mfa_challenge,
    pagination_info,
)

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = 1.0


@dataclass
class AuthState:
    """Mutable authentication state shared across requests."""

    session: requests.Session
    auth_method: str = "gpg"
    csrf_token: str | None = None
    jwt_access_token: str | None = None
    jwt_refresh_token: str | None = None
    user_id: str | None = None
    mfa_verified: bool = False
    reauthenticate: Callable[[], None] | None = field(default=None, repr=False)
    handle_mfa: Callable[[dict[str, Any] | None], None] | None = field(
        default=None, repr=False
    )


class PassboltHTTPClient:
    """HTTP client that adds CSRF, cookies, JWT, MFA, and pagination."""

    def __init__(self, base_url: str, auth_state: AuthState) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = auth_state

    def _update_csrf_from_response(self, response: requests.Response) -> None:
        for cookie in response.cookies:
            if cookie.name == "csrfToken":
                self.auth.csrf_token = cookie.value

        if not self.auth.csrf_token:
            csrf_cookie = self.auth.session.cookies.get("csrfToken")
            if csrf_cookie:
                self.auth.csrf_token = csrf_cookie

    def _prepare_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        prepared = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if headers:
            prepared.update(headers)

        if self.auth.csrf_token:
            prepared["X-CSRF-Token"] = self.auth.csrf_token

        if self.auth.jwt_access_token:
            prepared["Authorization"] = f"Bearer {self.auth.jwt_access_token}"

        return prepared

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        timeout: int = REQUEST_TIMEOUT,
        allow_mfa_retry: bool = True,
        allow_reauth: bool = True,
    ) -> Any:
        """Make an authenticated API request and return the parsed JSON body."""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        last_exception: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = self.auth.session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=self._prepare_headers(),
                    timeout=timeout,
                )
                self._update_csrf_from_response(response)

                payload: Any
                try:
                    payload = response.json()
                except ValueError:
                    response.raise_for_status()
                    raise APIError(
                        "API returned a non-JSON response",
                        status_code=response.status_code,
                        url=endpoint,
                        body=response.text[:500],
                    ) from None

                header = extract_header(payload)
                if is_mfa_challenge(header):
                    if not allow_mfa_retry or self.auth.handle_mfa is None:
                        raise MFARequiredError(
                            str(header.get("message", "MFA verification required")),
                            status_code=header.get("code"),
                            url=str(header.get("url", "")),
                            body=payload.get("body") if isinstance(payload, dict) else payload,
                        )
                    self.auth.handle_mfa(
                        payload.get("body") if isinstance(payload, dict) else None
                    )
                    self.auth.mfa_verified = True
                    return self.request(
                        method,
                        endpoint,
                        params=params,
                        json=json,
                        timeout=timeout,
                        allow_mfa_retry=False,
                        allow_reauth=allow_reauth,
                    )

                if response.status_code == 401 and allow_reauth:
                    if self.auth.reauthenticate is not None:
                        self.auth.reauthenticate()
                        return self.request(
                            method,
                            endpoint,
                            params=params,
                            json=json,
                            timeout=timeout,
                            allow_mfa_retry=allow_mfa_retry,
                            allow_reauth=False,
                        )

                try:
                    return ensure_success(payload)
                except APIError:
                    if response.status_code == 401 and allow_reauth:
                        if self.auth.reauthenticate is not None:
                            self.auth.reauthenticate()
                            return self.request(
                                method,
                                endpoint,
                                params=params,
                                json=json,
                                timeout=timeout,
                                allow_mfa_retry=allow_mfa_retry,
                                allow_reauth=False,
                            )
                    raise
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                last_exception = exc
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (2**attempt))

        raise APIError(
            f"Request failed after {MAX_RETRIES} retries: {last_exception}",
            url=endpoint,
        )

    def request_paginated(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> list[Any]:
        """Fetch all pages for a paginated collection endpoint."""
        query = dict(params or {})
        page = int(query.pop("page", 1) or 1)
        collected: list[Any] = []

        while True:
            page_params = dict(query)
            page_params["page"] = page
            url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
            response = self.auth.session.request(
                method,
                url,
                params=page_params,
                json=json,
                headers=self._prepare_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            self._update_csrf_from_response(response)
            response.raise_for_status()
            payload = response.json()
            body = ensure_success(payload)
            if not isinstance(body, list):
                return body if body is not None else []

            collected.extend(body)
            pagination = pagination_info(extract_header(payload))
            if not pagination:
                break

            total = int(pagination.get("count", len(collected)))
            limit = pagination.get("limit")
            if limit in (None, 0) or len(collected) >= total:
                break
            if len(body) == 0:
                break
            page += 1

        return collected