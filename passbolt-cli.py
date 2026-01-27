#!/usr/bin/env python3
"""
Passbolt CLI - A command-line interface for Passbolt password manager
"""

import argparse
import sys
from pathlib import Path

from passbolt.client import PassboltClient
from passbolt.config import load_config, PassboltConfig
from passbolt.commands import copy_password, search_passwords, export_password, show_password


def main() -> None:
    """Main entry point for the CLI"""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Passbolt CLI - Manage passwords from the command line',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-c', '--config',
        default='~/.config/passbolt/config.ini',
        help='Path to configuration file (default: ~/.config/passbolt/config.ini)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Copy command
    copy_parser = subparsers.add_parser('copy', help='Copy password to clipboard')
    copy_parser.add_argument('password_name', help='Name of the password to copy')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for passwords')
    search_parser.add_argument('query', help='Search query')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Display password on stdout')
    show_parser.add_argument('password_name', help='Name or UUID of the password to show')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export password to pass (password-store)')
    export_parser.add_argument('password_name', help='Name of the password in Passbolt')
    export_parser.add_argument('pass_path', help='Path in password-store')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Load configuration
    try:
        config_path: Path = Path(args.config).expanduser()
        config: PassboltConfig = load_config(config_path)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}", file=sys.stderr)
        print("Please create a configuration file. See config.ini.example", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Initialize Passbolt client
    try:
        client: PassboltClient = PassboltClient(config)
    except Exception as e:
        print(f"Error initializing Passbolt client: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Execute command
    try:
        match args.command:
            case 'copy':
                copy_password(client, args.password_name, config)
            case 'search':
                search_passwords(client, args.query)
            case 'show':
                show_password(client, args.password_name)
            case 'export':
                export_password(client, args.password_name, args.pass_path)
    except KeyboardInterrupt:
        print("\nOperation cancelled", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
