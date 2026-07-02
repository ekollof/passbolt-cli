#!/usr/bin/env python3
"""
Passbolt CLI - A command-line interface for Passbolt password manager
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from passbolt.argv import apply_default_copy_command
from passbolt.client import PassboltClient
from passbolt.commands import (
    copy_password,
    copy_totp,
    export_password,
    list_passwords,
    search_passwords,
    show_password,
)
from passbolt.config import default_config_path, load_config
from passbolt.tui import run_tui

def _add_pick_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pick",
        action="store_true",
        help="Interactively choose when multiple resources match",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "-c",
        "--config",
        default=str(default_config_path()),
        help="Path to configuration file",
    )
    global_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Reduce output (show: password only; copy: no status messages)",
    )

    parser = argparse.ArgumentParser(
        description="Passbolt CLI - Manage passwords from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  passbolt my-login          Copy password (default action)\n"
            "  passbolt copy my-login     Copy password explicitly\n"
            "  passbolt show my-login -q  Print only the password\n"
            "  passbolt search api --json Machine-readable search results"
        ),
        parents=[global_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    copy_parser = subparsers.add_parser(
        "copy",
        help="Copy password to clipboard",
        parents=[global_parser],
    )
    copy_parser.add_argument(
        "password_name", help="Name or UUID of the password to copy"
    )
    _add_pick_argument(copy_parser)

    list_parser = subparsers.add_parser(
        "list", help="List all passwords", parents=[global_parser]
    )
    list_parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )

    search_parser = subparsers.add_parser(
        "search", help="Search for passwords", parents=[global_parser]
    )
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--json", action="store_true", help="Output results as JSON"
    )

    show_parser = subparsers.add_parser(
        "show", help="Display password on stdout", parents=[global_parser]
    )
    show_parser.add_argument(
        "password_name", help="Name or UUID of the password to show"
    )
    _add_pick_argument(show_parser)

    export_parser = subparsers.add_parser(
        "export",
        help="Export password to pass (password-store)",
        parents=[global_parser],
    )
    export_parser.add_argument(
        "password_name", help="Name or UUID of the password in Passbolt"
    )
    export_parser.add_argument("pass_path", help="Path in password-store")
    _add_pick_argument(export_parser)

    totp_parser = subparsers.add_parser(
        "totp", help="Generate and copy TOTP code", parents=[global_parser]
    )
    totp_parser.add_argument(
        "password_name", help="Name or UUID of the resource with TOTP"
    )
    _add_pick_argument(totp_parser)

    subparsers.add_parser(
        "tui", help="Launch interactive terminal UI", parents=[global_parser]
    )

    return parser


def main() -> None:
    """Main entry point for the CLI"""
    apply_default_copy_command()
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    config_path = Path(args.config).expanduser()

    try:
        config = load_config(config_path)
    except FileNotFoundError:
        print(
            f"Error: Configuration file not found at {config_path}",
            file=sys.stderr,
        )
        print(
            "Please create a configuration file. See config.ini.example",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        client = PassboltClient(config)
    except Exception as e:
        print(f"Error initializing Passbolt client: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        match args.command:
            case "copy":
                copy_password(
                    client,
                    args.password_name,
                    config,
                    pick=args.pick,
                    quiet=args.quiet,
                )
            case "list":
                list_passwords(
                    client,
                    json_output=args.json,
                    quiet=args.quiet,
                )
            case "search":
                search_passwords(
                    client,
                    args.query,
                    json_output=args.json,
                    quiet=args.quiet,
                )
            case "show":
                show_password(
                    client,
                    args.password_name,
                    pick=args.pick,
                    quiet=args.quiet,
                )
            case "export":
                export_password(
                    client,
                    args.password_name,
                    args.pass_path,
                    pick=args.pick,
                )
            case "totp":
                copy_totp(
                    client,
                    args.password_name,
                    config,
                    pick=args.pick,
                    quiet=args.quiet,
                )
            case "tui":
                run_tui(client, config)
    except KeyboardInterrupt:
        print("\nOperation cancelled", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()