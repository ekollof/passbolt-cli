"""Tests for metadata normalization helpers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from passbolt.metadata import MetadataService, _resource_uri


class MetadataHelperTests(unittest.TestCase):
    def test_resource_uri_prefers_uri_field(self) -> None:
        self.assertEqual(_resource_uri({"uri": "https://example.com"}), "https://example.com")

    def test_resource_uri_falls_back_to_uris_array(self) -> None:
        self.assertEqual(
            _resource_uri({"uris": ["https://first.example", "https://second.example"]}),
            "https://first.example",
        )

    def test_normalize_v4_resource_unchanged(self) -> None:
        service = MetadataService(MagicMock(), MagicMock(), "user-id")
        resource = {"id": "1", "name": "GitHub", "username": "alice"}
        self.assertEqual(service.normalize_resource(resource), resource)


if __name__ == "__main__":
    unittest.main()