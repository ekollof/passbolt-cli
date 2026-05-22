# AGENTS.md - Passbolt CLI

## Project Overview

A command-line interface for Passbolt password manager, designed to work similarly to password-store (`pass`). The tool is read-only (no create/modify operations) and provides both CLI commands and an interactive TUI.

## Architecture

```
passbolt/
├── __init__.py       # Package init
├── auth.py           # GPG authentication with Passbolt server
├── client.py         # HTTP API client for Passbolt REST API
├── commands.py       # CLI command implementations (copy, search, show, export)
├── config.py         # INI configuration parsing and validation
├── cli.py            # Argument parsing and main entry point
├── theme.py          # Wallust/pywal theme loader for TUI
└── tui.py            # Textual-based TUI application (interactive mode)
```

## Key Design Decisions

### Read-Only
- This tool only reads passwords from Passbolt
- No create, modify, or delete operations are implemented
- This is intentional for security and scope

### Clipboard Handling
- Uses daemon-style clipboard tools: `wl-copy` (Wayland), `xclip`/`xsel` (X11), `pbcopy` (macOS)
- **CRITICAL**: These tools stay running to serve clipboard content
- **MUST** use `subprocess.Popen(stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL)` + `wait(timeout=0.5)`
- **NEVER** use `subprocess.run(stdout=PIPE, stderr=PIPE)` — this causes `communicate()` to block forever waiting for pipe EOF from a daemon that never exits
- This was the root cause of the terminal-hang-on-exit bug

### TUI Architecture
- Built with Textual (`textual>=0.50.0`)
- Clipboard operations run in background via `@work(thread=True)` to keep UI responsive
- Notifications use Textual's `notify()` plus `notify-send` for desktop notifications
- Search box filters in real-time; `Escape`/`Enter` defocus without clearing results
- Theming: Supports wallust/pywal dynamic theming via `~/.cache/wal/colors.json`

## Development

### Dependencies
- `requests>=2.31.0` — HTTP client
- `python-gnupg>=0.5.0` — GPG integration
- `textual>=0.50.0` — TUI framework

### Python Version
Requires Python **3.10+**. Uses 3.10+ features:
- `from __future__ import annotations` in all modules
- Union types with `|` syntax (`str | None` instead of `Optional[str]`)
- `match/case` instead of long if/elif/else chains
- Built-in generic types (`list[str]`, `dict[str, Any]` instead of `List[str]`, `Dict[str, Any]`)

### Running Locally
```bash
pip install -e .
passbolt --help
```

### Testing the TUI
```bash
passbolt tui
```

## Configuration

INI file at `~/.config/passbolt/config.ini`:

```ini
[passbolt]
server_url = https://passbolt.example.com
username = user@example.com
private_key_path = ~/.passbolt/private_key.asc
passphrase = exec:pass show passbolt/gpg-passphrase
clipboard_timeout = 45
```

Required: `server_url`, `username`, `private_key_path`
Optional: `passphrase`, `clipboard_timeout` (default 45s), `user_fingerprint`

## Common Issues

### Terminal hangs on exit after copy
- Cause: `subprocess.run()` blocking on daemon clipboard tools
- Fix: Use `subprocess.Popen` + `stdout=DEVNULL` + `stderr=DEVNULL` + short `wait()` timeout

### TUI search not filtering
- Check that the DataTable widget has focus after typing
- Ensure `on_data_table_row_selected` is connected

### GPG authentication fails
- Verify private key matches Passbolt account
- Check server URL is accessible
- Ensure passphrase is correct

## Code Style
- Type hints throughout (`typing` module)
- f-strings for formatting
- Black-compatible formatting (implied by pyproject.toml)
- Error handling with specific exceptions

## Building/Installing
```bash
uv tool install -e .     # Recommended
pipx install -e .        # Alternative
pip install -e .         # Development mode
```
