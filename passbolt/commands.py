"""Command implementations for Passbolt CLI"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from passbolt.clipboard import (
    copy_to_clipboard,
    get_clipboard_cmd,
    schedule_clipboard_clear,
)
from passbolt.client import PassboltClient
from passbolt.config import PassboltConfig
from passbolt.secret import (
    get_password_field,
    get_totp_for_resource,
    has_totp,
    parse_secret,
)


class AmbiguousResourceError(Exception):
    """Raised when multiple resources match a lookup."""

    def __init__(self, matches: list[dict[str, Any]]) -> None:
        self.matches = matches
        names = [resource.get("name", "Unknown") for resource in matches[:5]]
        super().__init__(f"Multiple resources match: {', '.join(names)}")


def _resource_summary(resource: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable resource summary."""
    return {
        "id": resource.get("id", ""),
        "name": resource.get("name", "Unknown"),
        "username": resource.get("username", ""),
        "uri": resource.get("uri", ""),
        "description": resource.get("description", ""),
        "has_totp": has_totp(resource),
    }


def pick_resource(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Interactively pick a resource when multiple matches exist."""
    if not sys.stdin.isatty():
        raise AmbiguousResourceError(matches)

    print("Multiple resources match:", file=sys.stderr)
    for index, resource in enumerate(matches, start=1):
        name = resource.get("name", "Unknown")
        username = resource.get("username", "")
        suffix = f" ({username})" if username else ""
        print(f"  {index}. {name}{suffix}", file=sys.stderr)

    while True:
        try:
            choice = input("Select [1-{}]: ".format(len(matches)))
            selected = int(choice)
            if 1 <= selected <= len(matches):
                return matches[selected - 1]
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            sys.exit(130)
        except ValueError:
            pass
        print("Invalid selection, try again.", file=sys.stderr)


def resolve_resource(
    client: PassboltClient, identifier: str, pick: bool = False
) -> dict[str, Any]:
    """Resolve a resource by UUID or name, optionally prompting on ambiguity."""
    if len(identifier) == 36 and identifier.count("-") == 4:
        try:
            return client.get_resource_by_id(identifier)
        except Exception:
            pass

    matches = client.find_resources_by_name(identifier)
    if not matches:
        print(f"Error: Password '{identifier}' not found", file=sys.stderr)
        sys.exit(1)

    if len(matches) == 1:
        return matches[0]

    if pick:
        return pick_resource(matches)

    raise AmbiguousResourceError(matches)


def _copy_with_auto_clear(
    text: str,
    clipboard_cmd: list[str],
    config: PassboltConfig | None,
    resource_name: str,
    *,
    quiet: bool = False,
) -> None:
    """Copy text to clipboard and schedule automatic clearing."""
    copy_to_clipboard(text, clipboard_cmd)

    if config and config.clipboard_timeout > 0:
        schedule_clipboard_clear(
            clipboard_cmd,
            config.clipboard_timeout,
            text,
            f"Clipboard cleared ({resource_name})",
        )
        if not quiet:
            print(
                f"Clipboard will be cleared in {config.clipboard_timeout} seconds",
                file=sys.stderr,
            )


def copy_password(
    client: PassboltClient,
    password_name: str,
    config: PassboltConfig | None = None,
    *,
    pick: bool = False,
    quiet: bool = False,
) -> None:
    """Copy a password to the clipboard"""
    try:
        resource = resolve_resource(client, password_name, pick=pick)
    except AmbiguousResourceError as error:
        print(f"Error: {error}", file=sys.stderr)
        print("Use --pick to choose interactively.", file=sys.stderr)
        sys.exit(1)

    try:
        resource_id: str = resource["id"]
        secret: str = client.get_secret(resource_id)
        password: str = get_password_field(secret)

        clipboard_cmd = get_clipboard_cmd()

        if not clipboard_cmd:
            print(
                "Error: No clipboard tool found (install xclip, xsel, wl-clipboard, or pbcopy)",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            _copy_with_auto_clear(
                password,
                clipboard_cmd,
                config,
                resource["name"],
                quiet=quiet,
            )
        except Exception as e:
            print(f"Error copying to clipboard: {e}", file=sys.stderr)
            sys.exit(1)

        if not quiet:
            print(f"Password for '{resource['name']}' copied to clipboard")

    except Exception as e:
        print(f"Error retrieving password: {e}", file=sys.stderr)
        sys.exit(1)


def list_passwords(
    client: PassboltClient,
    *,
    json_output: bool = False,
    quiet: bool = False,
) -> None:
    """List all password resources."""
    try:
        results = client.list_resources()
        if json_output:
            print(json.dumps([_resource_summary(resource) for resource in results]))
            return

        if not results:
            if not quiet:
                print("No passwords found")
            return

        if not quiet:
            print(f"Found {len(results)} password(s):\n")

        for resource in results:
            name = resource.get("name", "Unknown")
            totp_marker = " [TOTP]" if has_totp(resource) else ""
            if quiet:
                print(name)
            else:
                print(f"  • {name}{totp_marker}")
                resource_id = resource.get("id", "")
                if resource_id:
                    print(f"    ID: {resource_id}")
                username = resource.get("username", "")
                if username:
                    print(f"    Username: {username}")
                uri = resource.get("uri", "")
                if uri:
                    print(f"    URI: {uri}")
                print()

    except Exception as e:
        print(f"Error listing passwords: {e}", file=sys.stderr)
        sys.exit(1)


def search_passwords(
    client: PassboltClient,
    query: str,
    *,
    json_output: bool = False,
    quiet: bool = False,
) -> None:
    """Search for passwords matching the query"""
    try:
        results: list[dict[str, Any]] = client.search_resources(query)

        if json_output:
            print(json.dumps([_resource_summary(resource) for resource in results]))
            return

        if not results:
            if not quiet:
                print(f"No passwords found matching '{query}'")
            return

        if not quiet:
            print(f"Found {len(results)} password(s):\n")

        for resource in results:
            name = resource.get("name", "Unknown")
            resource_id = resource.get("id", "")
            username = resource.get("username", "")
            uri = resource.get("uri", "")
            description = resource.get("description", "")
            totp_marker = " [TOTP]" if has_totp(resource) else ""

            if quiet:
                print(name)
                continue

            print(f"  • {name}{totp_marker}")
            print(f"    ID: {resource_id}")
            if username:
                print(f"    Username: {username}")
            if uri:
                print(f"    URI: {uri}")
            if description:
                print(f"    Description: {description}")
            print()

    except Exception as e:
        print(f"Error searching passwords: {e}", file=sys.stderr)
        sys.exit(1)


def export_password(
    client: PassboltClient,
    password_name: str,
    pass_path: str,
    *,
    pick: bool = False,
) -> None:
    """Export a password to password-store (pass)"""
    try:
        resource = resolve_resource(client, password_name, pick=pick)
    except AmbiguousResourceError as error:
        print(f"Error: {error}", file=sys.stderr)
        print("Use --pick to choose interactively.", file=sys.stderr)
        sys.exit(1)

    try:
        resource_id = resource["id"]
        secret = client.get_secret(resource_id)
        secret_data = parse_secret(secret)

        password = secret_data.get("password", secret)
        username = resource.get("username", "")
        uri = resource.get("uri", "")

        pass_content = password
        if username or uri:
            pass_content += "\n"
        if username:
            pass_content += f"username: {username}\n"
        if uri:
            pass_content += f"url: {uri}\n"

        result = subprocess.run(
            ["pass", "insert", "-m", pass_path],
            input=pass_content,
            text=True,
            capture_output=True,
        )

        if result.returncode == 0:
            print(f"Password exported to pass as '{pass_path}'")
        else:
            print(f"Error exporting to pass: {result.stderr}", file=sys.stderr)
            sys.exit(1)

    except FileNotFoundError:
        print("Error: 'pass' (password-store) is not installed", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error exporting password: {e}", file=sys.stderr)
        sys.exit(1)


def show_password(
    client: PassboltClient,
    password_name: str,
    *,
    pick: bool = False,
    quiet: bool = False,
) -> None:
    """Display password on stdout"""
    try:
        resource = resolve_resource(client, password_name, pick=pick)
    except AmbiguousResourceError as error:
        print(f"Error: {error}", file=sys.stderr)
        print("Use --pick to choose interactively.", file=sys.stderr)
        sys.exit(1)

    try:
        resource_id = resource["id"]
        secret = client.get_secret(resource_id)
        secret_data = parse_secret(secret)

        password = secret_data.get("password", secret)
        if quiet:
            print(password)
            return

        username = resource.get("username", "")
        uri = resource.get("uri", "")

        output = password
        if username or uri:
            output += "\n"
        if username:
            output += f"username: {username}\n"
        if uri:
            output += f"url: {uri}\n"
        print(output, end="")
    except Exception as e:
        print(f"Error retrieving password: {e}", file=sys.stderr)
        sys.exit(1)


def copy_totp(
    client: PassboltClient,
    password_name: str,
    config: PassboltConfig | None = None,
    *,
    pick: bool = False,
    quiet: bool = False,
) -> None:
    """Generate and copy a TOTP code to the clipboard"""
    try:
        resource = resolve_resource(client, password_name, pick=pick)
    except AmbiguousResourceError as error:
        print(f"Error: {error}", file=sys.stderr)
        print("Use --pick to choose interactively.", file=sys.stderr)
        sys.exit(1)

    if not has_totp(resource):
        print(
            f"Error: '{resource.get('name', password_name)}' does not have TOTP data",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        resource_id: str = resource["id"]
        secret: str = client.get_secret(resource_id)
        totp_code = get_totp_for_resource(secret)

        if totp_code is None:
            print(
                f"Error: Could not extract TOTP from '{resource.get('name', password_name)}'",
                file=sys.stderr,
            )
            sys.exit(1)

        clipboard_cmd = get_clipboard_cmd()

        if not clipboard_cmd:
            print(totp_code)
            return

        try:
            _copy_with_auto_clear(
                totp_code,
                clipboard_cmd,
                config,
                f"TOTP for '{resource['name']}'",
                quiet=quiet,
            )
        except Exception as e:
            print(f"Error copying to clipboard: {e}", file=sys.stderr)
            print(totp_code)
            return

        if not quiet:
            print(f"TOTP code for '{resource['name']}' copied to clipboard")

    except Exception as e:
        print(f"Error generating TOTP: {e}", file=sys.stderr)
        sys.exit(1)