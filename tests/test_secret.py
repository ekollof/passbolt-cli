"""Tests for secret parsing and TOTP generation."""

from __future__ import annotations

import time
import unittest

from passbolt.secret import (
    extract_totp,
    generate_totp,
    get_password_field,
    has_totp,
    parse_secret,
)


class ParseSecretTests(unittest.TestCase):
    def test_json_secret(self) -> None:
        secret = '{"password": "s3cret", "description": "test"}'
        data = parse_secret(secret)
        self.assertEqual(data["password"], "s3cret")
        self.assertEqual(data["description"], "test")

    def test_plaintext_secret(self) -> None:
        self.assertEqual(parse_secret("plain")["password"], "plain")

    def test_get_password_field(self) -> None:
        self.assertEqual(
            get_password_field('{"password": "abc"}'),
            "abc",
        )
        self.assertEqual(get_password_field("fallback"), "fallback")


class TotpTests(unittest.TestCase):
    def test_has_totp(self) -> None:
        resource = {"resource_type_id": "05ba5c75-504d-5ad6-819a-83af68867d86"}
        self.assertTrue(has_totp(resource))
        self.assertFalse(has_totp({"resource_type_id": "other"}))

    def test_extract_totp(self) -> None:
        secret = (
            '{"password": "x", "totp": {"secret_key": "JBSWY3DPEHPK3PXP", '
            '"algorithm": "SHA1", "digits": 6, "period": 30}}'
        )
        params = extract_totp(secret)
        assert params is not None
        self.assertEqual(params["secret_key"], "JBSWY3DPEHPK3PXP")
        self.assertEqual(params["digits"], 6)

    def test_generate_totp_stable_within_step(self) -> None:
        code_a = generate_totp("JBSWY3DPEHPK3PXP", timestamp=30)
        code_b = generate_totp("JBSWY3DPEHPK3PXP", timestamp=59)
        self.assertEqual(len(code_a), 6)
        self.assertEqual(code_a, code_b)

    def test_generate_totp_changes_over_time(self) -> None:
        now = int(time.time())
        code_a = generate_totp("JBSWY3DPEHPK3PXP", timestamp=now)
        code_b = generate_totp("JBSWY3DPEHPK3PXP", timestamp=now + 30)
        self.assertNotEqual(code_a, code_b)


if __name__ == "__main__":
    unittest.main()