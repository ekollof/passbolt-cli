"""Tests for Passbolt API response helpers."""

from __future__ import annotations

import unittest

from passbolt.api_response import (
    APIError,
    ensure_success,
    extract_body,
    is_mfa_challenge,
    pagination_info,
)


class APIResponseTests(unittest.TestCase):
    def test_extract_body_from_envelope(self) -> None:
        payload = {"header": {"status": "success"}, "body": [{"id": "1"}]}
        self.assertEqual(extract_body(payload), [{"id": "1"}])

    def test_ensure_success_returns_body(self) -> None:
        payload = {
            "header": {"status": "success", "message": "ok", "code": 200, "url": "/x"},
            "body": ["a"],
        }
        self.assertEqual(ensure_success(payload), ["a"])

    def test_ensure_success_raises_on_error(self) -> None:
        payload = {
            "header": {
                "status": "error",
                "message": "nope",
                "code": 400,
                "url": "/resources.json",
            },
            "body": None,
        }
        with self.assertRaises(APIError):
            ensure_success(payload)

    def test_is_mfa_challenge(self) -> None:
        header = {"code": 403, "url": "/mfa/verify/error.json"}
        self.assertTrue(is_mfa_challenge(header))
        self.assertFalse(is_mfa_challenge({"code": 401, "url": "/auth/login.json"}))

    def test_pagination_info(self) -> None:
        header = {"pagination": {"count": 42, "page": 2, "limit": 20}}
        self.assertEqual(pagination_info(header), {"count": 42, "page": 2, "limit": 20})


if __name__ == "__main__":
    unittest.main()