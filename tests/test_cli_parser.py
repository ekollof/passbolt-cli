"""Tests for CLI argument parsing."""

from __future__ import annotations

import unittest

from passbolt.argv import KNOWN_COMMANDS, inject_default_copy_command


class DefaultCopyInjectionTests(unittest.TestCase):
    def test_injects_copy_for_bare_name(self) -> None:
        result = inject_default_copy_command(["passbolt", "my-login"])
        self.assertEqual(result, ["passbolt", "copy", "my-login"])

    def test_injects_copy_after_global_flags(self) -> None:
        result = inject_default_copy_command(
            ["passbolt", "-q", "-c", "~/.config/passbolt/config.ini", "my-login"]
        )
        self.assertEqual(
            result,
            ["passbolt", "-q", "-c", "~/.config/passbolt/config.ini", "copy", "my-login"],
        )

    def test_leaves_explicit_commands(self) -> None:
        result = inject_default_copy_command(["passbolt", "search", "api"])
        self.assertEqual(result, ["passbolt", "search", "api"])

    def test_known_commands_complete(self) -> None:
        self.assertIn("list", KNOWN_COMMANDS)


if __name__ == "__main__":
    unittest.main()