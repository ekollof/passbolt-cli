"""Tests for configuration parsing."""

from __future__ import annotations

import unittest

from passbolt.config import PassboltConfig, _parse_bool


class ConfigTests(unittest.TestCase):
    def test_parse_bool(self) -> None:
        self.assertTrue(_parse_bool("true"))
        self.assertFalse(_parse_bool("false"))

    def test_auth_method_validation(self) -> None:
        with self.assertRaises(ValueError):
            PassboltConfig(
                {
                    "server_url": "https://example.com",
                    "username": "user@example.com",
                    "private_key_path": "/tmp/key.asc",
                    "auth_method": "oauth",
                }
            )

    def test_jwt_requires_user_id(self) -> None:
        with self.assertRaises(ValueError):
            PassboltConfig(
                {
                    "server_url": "https://example.com",
                    "username": "user@example.com",
                    "private_key_path": "/tmp/key.asc",
                    "auth_method": "jwt",
                }
            )


if __name__ == "__main__":
    unittest.main()