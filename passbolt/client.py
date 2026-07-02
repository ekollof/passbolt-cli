"""Passbolt API client"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

import requests

from passbolt.auth import PassboltAuth
from passbolt.config import PassboltConfig
from passbolt.resources import match_resources_by_name

MAX_RETRIES = 3
RETRY_BACKOFF = 1.0  # seconds, doubled each retry
REQUEST_TIMEOUT = 30  # seconds, default for all HTTP requests


class PassboltClient:
    """Client for interacting with Passbolt API"""

    def __init__(self, config: PassboltConfig) -> None:
        self.config: PassboltConfig = config
        server_url = config.server_url
        assert server_url is not None
        self.base_url: str = server_url
        self.auth: PassboltAuth = PassboltAuth(config)
        self.session: requests.Session | None = None

    def _authenticate(self) -> None:
        """Authenticate with Passbolt API using GPG key"""
        try:
            self.session = self.auth.get_auth_token()
            self.session.headers.update(
                {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
        except Exception as e:
            raise Exception(f"Authentication failed: {e}")

    def _ensure_authenticated(self) -> requests.Session:
        """Authenticate lazily on first API request."""
        if self.session is None:
            self._authenticate()
        assert self.session is not None
        return self.session

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated request to the API with retry logic"""
        url = urljoin(self.base_url, endpoint)
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)

        last_exception: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                session = self._ensure_authenticated()
                response = session.request(method, url, **kwargs)

                # Handle session expiration
                match response.status_code:
                    case 401 | 403:
                        # Re-authenticate and retry
                        self._authenticate()
                        session = self._ensure_authenticated()
                        response = session.request(method, url, **kwargs)

                response.raise_for_status()
                return response
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (2**attempt))
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (2**attempt))

        raise Exception(f"Request failed after {MAX_RETRIES} retries: {last_exception}")

    def get_resources(
        self,
        filter_query: str | None = None,
        resource_type_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get list of password resources"""
        endpoint = "/resources.json"

        params = {}
        if filter_query:
            params["filter[search]"] = filter_query
        if resource_type_id:
            params["filter[has-resource-type-id]"] = resource_type_id

        response = self._make_request("GET", endpoint, params=params)
        data = response.json()

        # Passbolt API returns data in 'body' or directly
        if isinstance(data, dict) and "body" in data:
            return data["body"]
        return data if isinstance(data, list) else []

    def get_resource_by_id(self, resource_id: str) -> dict[str, Any]:
        """Get a specific resource by ID"""
        endpoint = f"/resources/{resource_id}.json"
        response = self._make_request("GET", endpoint)
        data = response.json()

        if isinstance(data, dict) and "body" in data:
            return data["body"]
        return data

    def get_secret(self, resource_id: str) -> str:
        """Get the decrypted secret for a resource"""
        endpoint = f"/secrets/resource/{resource_id}.json"
        response = self._make_request("GET", endpoint)
        data = response.json()

        # Extract encrypted secret
        if isinstance(data, dict) and "body" in data:
            encrypted_data = data["body"]["data"]
        elif isinstance(data, dict) and "data" in data:
            encrypted_data = data["data"]
        else:
            encrypted_data = data

        # Decrypt using GPG
        decrypted = self.auth.decrypt_secret(str(encrypted_data))
        return decrypted

    def search_resources(self, query: str) -> list[dict[str, Any]]:
        """Search for resources matching query"""
        # Try server-side filtering first
        resources = self.get_resources(filter_query=query or None)

        if not query:
            return resources

        query_lower = query.lower()
        filtered = []
        for resource in resources:
            # Search in name, username, uri, and description
            name = (resource.get("name") or "").lower()
            username = (resource.get("username") or "").lower()
            uri = (resource.get("uri") or "").lower()
            description = (resource.get("description") or "").lower()

            if (
                query_lower in name
                or query_lower in username
                or query_lower in uri
                or query_lower in description
            ):
                filtered.append(resource)

        return filtered

    def find_resources_by_name(self, name: str) -> list[dict[str, Any]]:
        """Find resources by exact or partial name match using server-side search."""
        return match_resources_by_name(self.search_resources(name), name)

    def find_resource_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a resource by exact or partial name match"""
        matches = self.find_resources_by_name(name)

        match len(matches):
            case 0:
                return None
            case 1:
                return matches[0]
            case _:
                names = [resource["name"] for resource in matches[:5]]
                raise ValueError(
                    f"Multiple resources match '{name}': {', '.join(names)}"
                )

    def find_resource_by_name_or_id(self, identifier: str) -> dict[str, Any] | None:
        """Find a resource by UUID or name"""
        # Check if it looks like a UUID (contains hyphens and is 36 chars)
        if len(identifier) == 36 and identifier.count("-") == 4:
            # Try to fetch by ID directly
            try:
                return self.get_resource_by_id(identifier)
            except (requests.exceptions.HTTPError, ValueError):
                pass

        # Fall back to name search
        return self.find_resource_by_name(identifier)

    def list_resources(self) -> list[dict[str, Any]]:
        """List all resources sorted by name."""
        resources = self.get_resources()
        return sorted(resources, key=lambda resource: (resource.get("name") or "").lower())