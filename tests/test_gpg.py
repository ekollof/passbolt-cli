"""Tests for GPG helper utilities."""

from __future__ import annotations

import unittest

from passbolt.gpg_util import (
    check_auth_token_format,
    decode_gpgauth_header_value,
    make_gpgauth_token,
    normalize_fingerprint,
)


class GPGHelperTests(unittest.TestCase):
    def test_normalize_fingerprint(self) -> None:
        self.assertEqual(
            normalize_fingerprint("ABCD-1234 5678"),
            "ABCD12345678",
        )

    def test_check_auth_token_format_valid(self) -> None:
        token = make_gpgauth_token()
        check_auth_token_format(token)

    def test_check_auth_token_format_invalid(self) -> None:
        with self.assertRaises(ValueError):
            check_auth_token_format("invalid")

    def test_decode_gpgauth_header_value(self) -> None:
        encoded = "abc%2Bdef%0Aghi"
        self.assertEqual(decode_gpgauth_header_value(encoded), "abc+def\nghi")


if __name__ == "__main__":
    unittest.main()