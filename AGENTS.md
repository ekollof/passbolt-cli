# AGENTS.md - Passbolt CLI

## Project Overview

A command-line interface for Passbolt password manager, designed to work similarly to password-store (`pass`). The tool is read-only (no create/modify operations) and provides both CLI commands and an interactive TUI.

## Architecture

```
passbolt/
├── __init__.py       # Package init
├── argv.py           # pass-style default command injection
├── api_response.py   # API envelope parsing, MFA detection
├── auth.py           # GPG/JWT authentication, MFA, server verify
├── cli.py            # Argument parsing and main entry point
├── client.py         # High-level API client (resources, secrets, search)
├── clipboard.py      # Clipboard copy/clear helpers
├── commands.py       # CLI command implementations (copy, search, show, export)
├── config.py         # INI configuration parsing and validation
├── gpg.py            # GPG encrypt/decrypt via python-gnupg
├── gpg_util.py       # GPGAuth token helpers (no gnupg import)
├── http.py           # Authenticated HTTP (CSRF, pagination, MFA retry)
├── metadata.py       # v5 encrypted metadata decryption
├── resources.py      # Resource name matching helpers
├── secret.py         # Shared secret parsing and TOTP generation
├── theme.py          # Wallust/pywal theme loader for TUI
└── tui.py            # Textual-based TUI application (interactive mode)
```

### Request flow

1. `PassboltClient` lazily calls `PassboltAuth.authenticate()` on first API request.
2. `auth.py` performs GPGAuth or JWT login, optional server verify, MFA if challenged.
3. `http.py` adds `X-CSRF-Token`, handles pagination, retries on 401 (re-auth / JWT refresh).
4. `metadata.py` normalizes v5 resources (decrypt `metadata` → `name`/`username`/`uri`).
5. Secrets are decrypted with the user's GPG key in `auth.decrypt_secret()`.

## Key Design Decisions

### Read-Only
- This tool only reads passwords from Passbolt
- No create, modify, or delete operations are implemented
- This is intentional for security and scope

### API Compatibility (Passbolt 5.0)
- **CSRF**: `csrfToken` cookie sent as `X-CSRF-Token` on authenticated requests
- **Pagination**: `request_paginated()` loops on `header.pagination` for `/resources.json`
- **GPGAuth**: Stages 1–2 via `POST /auth/login.json`; optional stage 0 via `verify_server`
- **JWT**: `POST /auth/jwt/login.json` with GPG-signed challenge; refresh on expiry
- **MFA**: Detects `/mfa/verify/error.json`, posts to `/mfa/verify/totp.json`
- **v5 metadata**: Fetches `/metadata/keys.json`, decrypts per-resource `metadata` field

### TOTP Support
- TOTP is a Passbolt Pro feature; CE resources won't have TOTP data
- Resource types are identified by `resource_type_id` UUID
- TOTP codes are generated using standard library (`hmac`, `hashlib`, `base64`) — no external deps
- TOTP resources are marked with `[TOTP]` in search results
- TOTP secret structure: `{"totp": {"secret_key": "...", "algorithm": "SHA1", "digits": 6, "period": 30}}`
- `mfa_totp_secret` in config reuses `generate_totp()` for login MFA (distinct from resource TOTP)

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

### Running Tests
```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v
```

### Testing the TUI
```bash
passbolt tui
```

## Configuration

INI file at `~/.config/passbolt/config.ini` (or `PASSBOLT_CONFIG`):

```ini
[passbolt]
server_url = https://passbolt.example.com
username = user@example.com
private_key_path = ~/.passbolt/private_key.asc
passphrase = exec:pass show passbolt/gpg-passphrase
clipboard_timeout = 45
user_fingerprint = ABCDEF1234567890
user_id = 8bb80df5-700c-48ce-b568-85a60fc3c8f2
auth_method = auto
verify_server = false
mfa_totp_secret =
```

Required: `server_url`, `username`, `private_key_path`

Optional:
- `passphrase` — plain text or `exec:<command>`
- `clipboard_timeout` — default 45s
- `user_fingerprint` — disambiguate multiple keys in one file
- `user_id` — required for `auth_method = jwt`; auto-fetched for GPG
- `auth_method` — `auto` | `gpg` | `jwt` (default `auto`)
- `verify_server` — GPGAuth stage-0 server verification (default `false`)
- `mfa_totp_secret` — base32 secret for non-interactive login MFA

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

### MFA blocks non-interactive use
- Set `mfa_totp_secret` or use a service account without MFA
- MFA handler in `auth.py` prompts on TTY; raises if stdin is not a TTY

### v5 metadata decryption fails
- User needs metadata private keys from `/metadata/keys.json`
- Browser login provisions keys; shared keys must be imported for the account
- `metadata.py` uses full asymmetric decrypt (session key cache is best-effort prefetch only)

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