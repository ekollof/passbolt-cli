"""Tests for clipboard helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from passbolt.clipboard import clear_clipboard_if_unchanged


class ClipboardClearTests(unittest.TestCase):
    @patch("passbolt.clipboard.read_clipboard", return_value="secret")
    @patch("passbolt.clipboard.clear_clipboard")
    def test_clears_when_unchanged(self, mock_clear, _mock_read) -> None:
        self.assertTrue(clear_clipboard_if_unchanged(["wl-copy"], "secret"))
        mock_clear.assert_called_once_with(["wl-copy"])

    @patch("passbolt.clipboard.read_clipboard", return_value="other")
    @patch("passbolt.clipboard.clear_clipboard")
    def test_skips_when_changed(self, mock_clear, _mock_read) -> None:
        self.assertFalse(clear_clipboard_if_unchanged(["wl-copy"], "secret"))
        mock_clear.assert_not_called()

    @patch("passbolt.clipboard.read_clipboard", return_value=None)
    @patch("passbolt.clipboard.clear_clipboard")
    def test_skips_when_unreadable(self, mock_clear, _mock_read) -> None:
        self.assertFalse(clear_clipboard_if_unchanged(["wl-copy"], "secret"))
        mock_clear.assert_not_called()


if __name__ == "__main__":
    unittest.main()