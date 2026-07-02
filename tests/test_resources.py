"""Tests for resource lookup helpers."""

from __future__ import annotations

import unittest

from passbolt.resources import (
    filter_resources_by_query,
    match_resources_by_name,
    sanitize_resource_for_display,
)


class SanitizeResourceTests(unittest.TestCase):
    def test_null_fields_become_strings(self) -> None:
        resource = sanitize_resource_for_display(
            {"id": "1", "name": None, "username": None, "uri": None}
        )
        self.assertEqual(resource["name"], "Unknown")
        self.assertEqual(resource["username"], "")
        self.assertEqual(resource["uri"], "")

    def test_filters_null_name_without_error(self) -> None:
        resources = [{"id": "1", "name": None, "username": "alice"}]
        self.assertEqual(len(filter_resources_by_query(resources, "alice")), 1)


class FilterResourcesByQueryTests(unittest.TestCase):
    def test_empty_query_returns_all(self) -> None:
        resources = [{"id": "1", "name": "GitHub"}]
        self.assertEqual(filter_resources_by_query(resources, ""), resources)

    def test_filters_by_name_username_uri_description(self) -> None:
        resources = [
            {"id": "1", "name": "GitHub", "username": "alice"},
            {"id": "2", "name": "GitLab", "uri": "https://gitlab.example"},
            {"id": "3", "name": "Notes", "description": "aws root"},
        ]
        self.assertEqual(len(filter_resources_by_query(resources, "git")), 2)
        self.assertEqual(len(filter_resources_by_query(resources, "aws")), 1)


class MatchResourcesByNameTests(unittest.TestCase):
    def test_exact_match_preferred(self) -> None:
        resources = [
            {"id": "1", "name": "GitHub"},
            {"id": "2", "name": "GitHub Admin"},
        ]
        matches = match_resources_by_name(resources, "GitHub")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["id"], "1")

    def test_partial_match_returns_multiple(self) -> None:
        resources = [
            {"id": "1", "name": "GitHub"},
            {"id": "2", "name": "GitHub Admin"},
        ]
        matches = match_resources_by_name(resources, "git")
        self.assertEqual(len(matches), 2)


if __name__ == "__main__":
    unittest.main()