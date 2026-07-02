"""Tests for resource lookup helpers."""

from __future__ import annotations

import unittest

from passbolt.resources import match_resources_by_name


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