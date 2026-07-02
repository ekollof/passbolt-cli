"""CLI argv helpers."""

from __future__ import annotations

import sys

KNOWN_COMMANDS = frozenset(
    {"copy", "search", "show", "list", "export", "totp", "tui"}
)


def inject_default_copy_command(argv: list[str] | None = None) -> list[str]:
    """Treat `passbolt <name>` as `passbolt copy <name>` (pass-style)."""
    args = list(argv if argv is not None else sys.argv)
    index = 1
    while index < len(args):
        arg = args[index]
        if arg in ("-c", "--config"):
            index += 2
            continue
        if arg in ("-q", "--quiet"):
            index += 1
            continue
        if arg.startswith("-"):
            index += 1
            continue
        if arg in KNOWN_COMMANDS:
            return args
        args.insert(index, "copy")
        return args
    return args


def apply_default_copy_command() -> None:
    """Mutate sys.argv to insert the default copy subcommand when needed."""
    sys.argv[:] = inject_default_copy_command(sys.argv)