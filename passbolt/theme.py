"""Wallust/pywal theme support for Passbolt TUI"""

from __future__ import annotations

import json
from pathlib import Path

from textual.theme import Theme


def load_wallust_theme() -> Theme | None:
    """Load a Textual Theme from wallust/pywal colors in ~/.cache/wal/colors.json.

    Supports both pywal and wallust generated color schemes.
    Returns None if no colors.json is found or it cannot be parsed.
    """
    wal_path = Path.home() / ".cache" / "wal" / "colors.json"
    if not wal_path.exists():
        return None

    try:
        with wal_path.open("r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    special = data.get("special", {})
    colors = data.get("colors", {})

    background = special.get("background")
    foreground = special.get("foreground")

    if not background or not foreground:
        return None

    # Map wallust colorN palette to Textual theme colors
    return Theme(
        name="wallust",
        primary=colors.get("color4", "#757E97"),
        secondary=colors.get("color5", "#80899A"),
        accent=colors.get("color3", "#7B7585"),
        foreground=foreground,
        background=background,
        success=colors.get("color2", "#8C7A5D"),
        warning=colors.get("color11", "#948CA0"),
        error=colors.get("color1", "#6F7888"),
        surface=colors.get("color0", "#403F40"),
        panel=colors.get("color8", "#9B9DA1"),
        dark=True,
    )
