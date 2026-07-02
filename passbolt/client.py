"""Passbolt API client"""

from __future__ import annotations

from typing import Any

import requests

from passbolt.auth import PassboltAuth
from passbolt.config import PassboltConfig
from passbolt.http import AuthState, PassboltHTTPClient
from passbolt.metadata import MetadataService
from passbolt.resources import match_resources_by_name


class PassboltClient:
    """Client for interacting with Passbolt API"""

    def __init__(self, config: PassboltConfig) -> None:
        self.config: PassboltConfig = config
        server_url = config.server_url
        assert server_url is not None
        self.base_url: str = server_url
        self.auth: PassboltAuth = PassboltAuth(config)
        self._auth_state: AuthState | None = None
        self._http: PassboltHTTPClient | None = None
        self._metadata: MetadataService | None = None

    def _authenticate(self) -> None:
        """Authenticate with Passbolt API."""
        try:
            self._auth_state = self.auth.authenticate()
            assert self._auth_state is not None
            self._http = PassboltHTTPClient(self.base_url, self._auth_state)
            user_id = self._auth_state.user_id or self.config.user_id
            if not user_id:
                raise ValueError("Unable to determine Passbolt user id")
            self._metadata = MetadataService(self._http, self.auth.gpg, user_id)
            self._metadata.setup()
            if self._metadata.v5_enabled:
                self._metadata.prefetch_session_keys()
        except Exception as e:
            raise Exception(f"Authentication failed: {e}") from e

    def _ensure_authenticated(self) -> PassboltHTTPClient:
        """Authenticate lazily on first API request."""
        if self._http is None:
            self._authenticate()
        assert self._http is not None
        return self._http

    def _normalize_resources(self, resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self._metadata is None or not self._metadata.v5_enabled:
            return resources
        return self._metadata.normalize_resources(resources)

    def _normalize_resource(self, resource: dict[str, Any]) -> dict[str, Any]:
        if self._metadata is None or not self._metadata.v5_enabled:
            return resource
        return self._metadata.normalize_resource(resource)

    def get_resources(
        self,
        filter_query: str | None = None,
        resource_type_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get list of password resources with pagination."""
        endpoint = "/resources.json"

        params: dict[str, Any] = {}
        if filter_query:
            params["filter[search]"] = filter_query
        if resource_type_id:
            params["filter[has-resource-type-id]"] = resource_type_id

        http = self._ensure_authenticated()
        resources = http.request_paginated("GET", endpoint, params=params)
        if not isinstance(resources, list):
            return []
        return self._normalize_resources(resources)

    def get_resource_by_id(self, resource_id: str) -> dict[str, Any]:
        """Get a specific resource by ID"""
        endpoint = f"/resources/{resource_id}.json"
        http = self._ensure_authenticated()
        resource = http.request("GET", endpoint)
        if not isinstance(resource, dict):
            raise ValueError(f"Unexpected resource payload for {resource_id}")
        return self._normalize_resource(resource)

    def get_secret(self, resource_id: str) -> str:
        """Get the decrypted secret for a resource"""
        endpoint = f"/secrets/resource/{resource_id}.json"
        http = self._ensure_authenticated()
        data = http.request("GET", endpoint)

        if isinstance(data, dict) and "data" in data:
            encrypted_data = data["data"]
        else:
            encrypted_data = data

        return self.auth.decrypt_secret(str(encrypted_data))

    def search_resources(self, query: str) -> list[dict[str, Any]]:
        """Search for resources matching query"""
        resources = self.get_resources(filter_query=query or None)

        if not query:
            return resources

        query_lower = query.lower()
        filtered = []
        for resource in resources:
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
        if len(identifier) == 36 and identifier.count("-") == 4:
            try:
                return self.get_resource_by_id(identifier)
            except (requests.exceptions.HTTPError, ValueError):
                pass

        return self.find_resource_by_name(identifier)

    def list_resources(self) -> list[dict[str, Any]]:
        """List all resources sorted by name."""
        resources = self.get_resources()
        return sorted(resources, key=lambda resource: (resource.get("name") or "").lower())