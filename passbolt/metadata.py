"""v5 encrypted metadata decryption and resource normalization."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from passbolt.http import PassboltHTTPClient

if TYPE_CHECKING:
    from passbolt.gpg import GPGHelper


def _string_field(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else ""


def _resource_uri(metadata_fields: dict[str, Any]) -> str:
    uri = _string_field(metadata_fields, "uri")
    if uri:
        return uri
    uris = metadata_fields.get("uris")
    if isinstance(uris, list) and uris:
        first = uris[0]
        return first if isinstance(first, str) else ""
    return ""


class MetadataService:
    """Decrypt and normalize Passbolt v5 encrypted metadata."""

    def __init__(
        self,
        http: PassboltHTTPClient,
        gpg: GPGHelper,
        user_id: str,
    ) -> None:
        self.http = http
        self.gpg = gpg
        self.user_id = user_id
        self._metadata_keys: list[dict[str, Any]] | None = None
        self._decrypted_metadata_keys: dict[str, Any] = {}
        self._v5_enabled = False

    def setup(self) -> None:
        """Detect whether v5 metadata is enabled on the server."""
        try:
            settings = self.http.request("GET", "/settings.json")
            plugins = {}
            if isinstance(settings, dict):
                plugins = settings.get("passbolt", {}).get("plugins", {})
            metadata_plugin = plugins.get("metadata", {})
            self._v5_enabled = bool(metadata_plugin.get("enabled"))
        except Exception:
            self._v5_enabled = False

    @property
    def v5_enabled(self) -> bool:
        return self._v5_enabled

    def normalize_resources(self, resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Populate cleartext metadata fields for v5 resources."""
        return [self.normalize_resource(resource) for resource in resources]

    def normalize_resource(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Populate name/username/uri/description for encrypted-metadata resources."""
        if not resource.get("metadata"):
            return resource

        metadata_fields = self.decrypt_metadata(resource)
        normalized = dict(resource)
        normalized["name"] = _string_field(metadata_fields, "name")
        normalized["username"] = _string_field(metadata_fields, "username")
        normalized["uri"] = _resource_uri(metadata_fields)
        description = _string_field(metadata_fields, "description")
        if description:
            normalized["description"] = description
        return normalized

    def decrypt_metadata(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Decrypt a resource metadata blob and return the parsed JSON object."""
        encrypted_metadata = resource.get("metadata")
        if not encrypted_metadata:
            return {
                "name": resource.get("name", ""),
                "username": resource.get("username", ""),
                "uri": resource.get("uri", ""),
                "description": resource.get("description", ""),
            }

        metadata_key = self._metadata_decryptor(resource)
        decrypted = metadata_key.decrypt(str(encrypted_metadata))
        parsed = json.loads(decrypted)
        if not isinstance(parsed, dict):
            raise ValueError("Decrypted metadata is not a JSON object")
        return parsed

    def _metadata_decryptor(self, resource: dict[str, Any]) -> Any:
        metadata_key_type = resource.get("metadata_key_type")
        if metadata_key_type == "user_key":
            return self.gpg

        metadata_key_id = resource.get("metadata_key_id")
        if not metadata_key_id:
            raise ValueError("Encrypted metadata is missing metadata_key_id")

        if metadata_key_id in self._decrypted_metadata_keys:
            return self._decrypted_metadata_keys[metadata_key_id]

        metadata_private_key = self._find_metadata_private_key(str(metadata_key_id))
        encrypted_private_key_data = metadata_private_key["data"]
        decrypted_private_key_data = json.loads(
            self.gpg.decrypt(str(encrypted_private_key_data))
        )
        armored_key = decrypted_private_key_data["armored_key"]
        passphrase = decrypted_private_key_data.get("passphrase", "")

        from passbolt.gpg import GPGHelper

        metadata_gpg = GPGHelper(armored_key, passphrase=passphrase)
        self._decrypted_metadata_keys[metadata_key_id] = metadata_gpg
        return metadata_gpg

    def _find_metadata_private_key(self, metadata_key_id: str) -> dict[str, Any]:
        if self._metadata_keys is None:
            self._metadata_keys = self.http.request(
                "GET",
                "/metadata/keys.json",
                params={"contain[metadata_private_keys]": "1"},
            )
            if not isinstance(self._metadata_keys, list):
                self._metadata_keys = []

        for metadata_key in self._metadata_keys:
            if metadata_key.get("id") != metadata_key_id:
                continue
            private_keys = metadata_key.get("metadata_private_keys", [])
            for private_key in private_keys:
                if private_key.get("user_id") == self.user_id:
                    return private_key
            raise ValueError(
                f"No metadata private key for user {self.user_id} on key {metadata_key_id}"
            )

        raise ValueError(f"Metadata key not found: {metadata_key_id}")

    def prefetch_session_keys(self) -> int:
        """Best-effort prefetch of metadata session keys (optional optimization)."""
        try:
            session_keys = self.http.request("GET", "/metadata/session-keys.json")
        except Exception:
            return 0

        if not isinstance(session_keys, list):
            return 0

        count = 0
        for entry in session_keys:
            data = entry.get("data")
            if not data:
                continue
            try:
                decrypted = self.gpg.decrypt(str(data))
                payload = json.loads(decrypted)
                if payload.get("object_type") != "PASSBOLT_SESSION_KEYS":
                    continue
                count += len(payload.get("session_keys", []))
            except Exception:
                continue
        return count