"""Clipboard integration for Passbolt CLI"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

_CLEAR_WORKER = """import sys, time
from passbolt.clipboard import (
    clear_clipboard_if_unchanged,
    notify_clipboard_cleared,
)
expected = sys.stdin.read()
time.sleep({timeout})
if clear_clipboard_if_unchanged({clipboard_cmd!r}, expected):
    notify_clipboard_cleared({message!r})
"""


def get_clipboard_cmd() -> list[str] | None:
    """Return the clipboard command for the current session, if available."""
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        return ["wl-copy"]
    if os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            return ["xclip", "-selection", "clipboard", "-i"]
        if shutil.which("xsel"):
            return ["xsel", "--clipboard", "--input"]
    if shutil.which("pbcopy"):
        return ["pbcopy"]
    return None


def get_clipboard_read_cmd() -> list[str] | None:
    """Return the clipboard read command for the current session, if available."""
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        return ["wl-paste", "--no-newline"]
    if os.environ.get("DISPLAY"):
        if shutil.which("xclip"):
            return ["xclip", "-selection", "clipboard", "-o"]
        if shutil.which("xsel"):
            return ["xsel", "--clipboard", "--output"]
    if shutil.which("pbpaste"):
        return ["pbpaste"]
    return None


def copy_to_clipboard(text: str, clipboard_cmd: list[str]) -> None:
    """Copy text to clipboard without blocking on daemon-style tools."""
    proc = subprocess.Popen(
        clipboard_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if proc.stdin is not None:
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
    try:
        proc.wait(timeout=0.5)
        if proc.returncode != 0:
            raise RuntimeError(f"Clipboard error (exit {proc.returncode})")
    except subprocess.TimeoutExpired:
        pass  # Daemon-style clipboard tool, expected


def read_clipboard() -> str | None:
    """Read text from the system clipboard."""
    read_cmd = get_clipboard_read_cmd()
    if not read_cmd:
        return None
    try:
        result = subprocess.run(
            read_cmd,
            capture_output=True,
            timeout=2,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.decode("utf-8", errors="replace")
    except (subprocess.TimeoutExpired, OSError):
        return None


def clear_clipboard(clipboard_cmd: list[str]) -> None:
    """Clear the system clipboard."""
    if clipboard_cmd[0] == "wl-copy":
        proc = subprocess.Popen(
            ["wl-copy", "--clear"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            clipboard_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.stdin is not None:
            proc.stdin.write(b"")
            proc.stdin.close()

    try:
        proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass  # Daemon-style clipboard tool, expected


def clear_clipboard_if_unchanged(
    clipboard_cmd: list[str], expected_text: str
) -> bool:
    """Clear clipboard only if it still contains the expected text."""
    current = read_clipboard()
    if current is None or current != expected_text:
        return False
    clear_clipboard(clipboard_cmd)
    return True


def notify_clipboard_cleared(message: str = "Clipboard cleared") -> None:
    """Notify the user that the clipboard was cleared."""
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "Passbolt", message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def schedule_clipboard_clear(
    clipboard_cmd: list[str],
    timeout: int,
    expected_text: str,
    message: str = "Clipboard cleared",
) -> None:
    """Clear clipboard after timeout if content is unchanged."""
    clear_script = _CLEAR_WORKER.format(
        timeout=timeout,
        clipboard_cmd=clipboard_cmd,
        message=message,
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", clear_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    if proc.stdin is not None:
        proc.stdin.write(expected_text.encode("utf-8"))
        proc.stdin.close()