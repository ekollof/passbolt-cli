# Passbolt CLI

A command-line interface for [Passbolt](https://www.passbolt.com/) password manager, designed to work similarly to [password-store](https://www.passwordstore.org/) (`pass`).

## Features

- **Copy passwords to clipboard** - Quickly copy passwords without leaving the terminal
- **pass-style default command** - `passbolt <name>` copies, just like `pass -c`
- **Search and list passwords** - Find passwords by name, username, URI, or description
- **TOTP support** - Generate and copy 2FA codes for TOTP-enabled resources
- **Interactive TUI** - Browse and search passwords in a terminal user interface
- **Export to pass** - Seamlessly migrate passwords to password-store
- **Auto-clear clipboard** - Clears sensitive data after a configurable timeout (default 45s)
- **Script-friendly output** - Quiet mode and JSON output for automation
- **GPG and JWT authentication** - GPGAuth by default with optional JWT fallback
- **Passbolt API 5.0 compatibility** - CSRF tokens, pagination, MFA, and v5 encrypted metadata
- **INI configuration** - Simple configuration file format

## Requirements

- Python 3.10 or higher
- GPG (GnuPG)
- Clipboard tool (one of):
  - Linux/Wayland: [wl-clipboard](https://github.com/bugaevc/wl-clipboard) (`wl-copy` / `wl-paste`)
  - Linux/X11: `xclip` or `xsel`
  - macOS: `pbcopy` / `pbpaste` (built-in)
- password-store (`pass`) - optional, only needed for the export command

## Installation

### Using uv (recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager and runtime. It installs tools in isolated environments:

```bash
# Install from git repository
uv tool install git+https://github.com/ekollof/passbolt-cli.git

# Or install from local directory
cd /path/to/passbolt-cli
uv tool install -e .
```

### Using pipx

[pipx](https://pipx.pypa.io/) installs Python applications in isolated environments:

```bash
# Install from git repository
pipx install git+https://github.com/ekollof/passbolt-cli.git

# Or install from local directory
cd /path/to/passbolt-cli
pipx install -e .
```

Both `uv` and `pipx` will install the `passbolt` command globally while keeping it isolated from other Python packages.

### Using pip

```bash
# Install from git repository
pip install git+https://github.com/ekollof/passbolt-cli.git

# Or install from local directory
pip install .

# Or install in development mode (editable)
pip install -e .
```

### Manual installation (without pip)

1. Clone this repository:
```bash
git clone https://github.com/ekollof/passbolt-cli.git
cd passbolt-cli
```

2. Install in development mode:
```bash
pip install -e .
```

3. Run directly with Python:
```bash
python -m passbolt copy <password-name>
# or
./passbolt-cli.py copy <password-name>
```

### Shell completion (bash)

```bash
source completions/passbolt.bash
```

Add that line to your `~/.bashrc` to enable tab completion for commands and flags.

## Configuration

1. Create the configuration directory:
```bash
mkdir -p ~/.config/passbolt
```

2. Copy the example configuration:
```bash
cp config.ini.example ~/.config/passbolt/config.ini
```

3. Edit the configuration file with your settings:
```bash
nano ~/.config/passbolt/config.ini
```

Required settings:
- `server_url`: Your Passbolt server URL (e.g., `https://passbolt.example.com`)
- `username`: Your Passbolt username (email address)
- `private_key_path`: Path to your GPG private key file

Optional settings:
- `passphrase`: Your GPG key passphrase (not recommended to store in plain text)
- `passphrase = exec:<command>`: Execute a command to retrieve the passphrase securely
- `clipboard_timeout`: Seconds before the clipboard is auto-cleared (default: `45`; set to `0` to disable)
- `user_fingerprint`: Your GPG key fingerprint (optional; use when you have multiple keys in the file)
- `user_id`: Your Passbolt user UUID (required for JWT auth; auto-fetched for GPG auth)
- `auth_method`: `auto` (default), `gpg`, or `jwt` — see [Authentication methods](#authentication-methods)
- `verify_server`: `true` or `false` (default `false`) — perform GPGAuth stage-0 server verification before login
- `mfa_totp_secret`: Base32 TOTP secret for non-interactive MFA (scripts/CI only)

You can also point at a config file via the `PASSBOLT_CONFIG` environment variable or the `-c` flag.

See `config.ini.example` for a fully commented template.

### Authentication methods

| `auth_method` | When to use |
|---------------|-------------|
| `auto` (default) | Most setups. Tries GPGAuth first, falls back to JWT if GPG fails. |
| `gpg` | Standard Passbolt instances with GPGAuth enabled (v4 and most v5 servers). |
| `jwt` | Servers that require or prefer JWT login. Requires `user_id` in config. |

GPGAuth is the usual choice and needs only `server_url`, `username`, and `private_key_path`. JWT is useful when GPGAuth is disabled or unreliable on your instance.

### Finding your `user_id`

Required only when `auth_method = jwt`. For GPG auth it is optional; the CLI fetches it from `/users/me.json` after login.

1. Log in to Passbolt in your browser.
2. Open your profile (avatar → **My profile**).
3. The user UUID appears in the profile URL or account details, e.g. `8bb80df5-700c-48ce-b568-85a60fc3c8f2`.

Alternatively, after a successful GPG login, inspect the JSON from `GET /users/me.json` (browser dev tools or `curl` with session cookies).

### MFA (multi-factor authentication)

If your account has TOTP MFA enabled:

- **Interactive use**: The CLI prompts for a code on first API access after login.
- **Scripts / CI**: Set `mfa_totp_secret` to the same base32 secret as your authenticator app (not the six-digit code).

```ini
# Example: automate MFA in a cron job or CI pipeline
mfa_totp_secret = JBSWY3DPEHPK3PXP
```

Treat `mfa_totp_secret` like a password: restrict config file permissions (`chmod 600`) and prefer `exec:` to load it from a secret store when possible.

### v5 encrypted metadata

On Passbolt v5 instances with encrypted metadata, resource names and URIs are stored in an encrypted `metadata` field instead of cleartext. The CLI decrypts these locally using metadata private keys from `/metadata/keys.json` and exposes the same `name`, `username`, and `uri` fields used by search and list.

No extra config is needed if:

- Your account has access to the shared metadata keys (same as the browser extension), and
- You use the same GPG private key registered in Passbolt.

If list/search returns empty names or decryption errors, log in via the browser extension once so metadata keys are provisioned, or ask your administrator to ensure shared metadata keys are distributed to your account.

### Secure Passphrase Retrieval

For better security, you can use the `exec:` prefix to execute a command that returns your passphrase:

```ini
# Retrieve from password-store
passphrase = exec:pass show passbolt/gpg-passphrase

# Retrieve from GNOME Keyring
passphrase = exec:secret-tool lookup passbolt passphrase

# Decrypt from a GPG-encrypted file
passphrase = exec:gpg --decrypt ~/.passbolt/passphrase.gpg
```

The command's stdout will be used as the passphrase, with trailing newlines automatically stripped.

### Obtaining Your Private Key

Your private key is the same key used for account recovery in the Passbolt browser extension:

1. Log in to Passbolt in your browser
2. Go to your profile settings
3. Navigate to "Keys" or "GPG Keys"
4. Export your private key
5. Save it to a secure location (e.g., `~/.passbolt/private_key.asc`)
6. Set appropriate permissions: `chmod 600 ~/.passbolt/private_key.asc`

## Usage

After installation with uv, pipx, or pip, the `passbolt` command will be available globally.

### Quick copy (pass-style)

The most common action works like `pass -c`:

```bash
passbolt gmail
```

This is equivalent to `passbolt copy gmail`.

### Copy a password to clipboard

```bash
passbolt copy <password-name-or-uuid>
```

Examples:
```bash
passbolt copy gmail
passbolt -q copy gmail          # No status messages on stderr
passbolt copy github --pick     # Interactively pick when multiple names match
```

The password is copied to your clipboard and automatically cleared after 45 seconds (configurable). Clearing is content-aware: if you copy something else in the meantime, the old secret is left alone.

### Show a password

```bash
passbolt show <password-name-or-uuid>
```

Examples:
```bash
passbolt show gmail
passbolt show gmail -q          # Password only, for scripting
```

Without `-q`, output is in pass-compatible format (password plus `username:` / `url:` lines).

### Generate a TOTP code

If a resource has TOTP data (2FA), generate and copy the code:

```bash
passbolt totp <password-name-or-uuid>
```

Example:
```bash
passbolt totp github
```

The TOTP code is copied to your clipboard (or printed to stdout if no clipboard tool is available). TOTP-enabled resources are marked with `[TOTP]` in search and list output.

### Search for passwords

```bash
passbolt search <query>
```

Examples:
```bash
passbolt search google
passbolt search api --json      # Machine-readable output
passbolt search aws -q          # Names only, one per line
```

### List all passwords

```bash
passbolt list
passbolt list --json
passbolt list -q                # Names only
```

### Interactive TUI

Launch a terminal user interface for browsing and searching passwords.

```bash
passbolt tui
```

Keyboard shortcuts:
- `↑` / `↓` - Navigate entries
- `/` - Focus search box
- `Tab` - Switch focus between search and results table
- `Enter` - Copy password (when the table is focused)
- `Esc` - Clear search filter, or move focus from search to results table
- `c` - Copy password to clipboard
- `t` - Copy TOTP code to clipboard
- `u` - Copy username to clipboard
- `o` - Copy URI to clipboard
- `s` - Show password on screen (`c`/`t`/`u`/`o` work from that screen too)
- `r` - Refresh resource list from server
- `q` - Quit

Search filters the loaded list instantly (no API call per keystroke). A status line shows how many entries match (e.g. `Showing 3 of 120 — filter: git`). TOTP entries show a live countdown and progress bar in the detail panel (e.g. `123456 (18s)`). After copying, the footer shows a clipboard clear countdown.

**Theming:** The TUI supports dynamic theming via [wallust](https://codeberg.org/explosion-mental/wallust) / [pywal](https://github.com/dylanaraps/pywal). If `~/.cache/wal/colors.json` exists, the TUI will automatically pick up your color scheme and refresh when it changes.

### Export to password-store

```bash
passbolt export <password-name-or-uuid> <pass-path>
```

Example:
```bash
passbolt export "My Gmail" Email/gmail
```

This exports the password to password-store at `Email/gmail`.

### Global flags

| Flag | Description |
|------|-------------|
| `-c`, `--config` | Path to configuration file |
| `-q`, `--quiet` | Reduce output (see per-command behaviour above) |
| `--pick` | Interactively choose when multiple resources match (`copy`, `show`, `totp`, `export`) |
| `--json` | JSON output (`search`, `list`) |

Environment variables:
- `PASSBOLT_CONFIG` - Default path to the configuration file

## Examples

```bash
# pass-style quick copy
passbolt github

# Show password for use in a script
passbolt show github -q

# Search and pipe to fzf
passbolt search -q "" | fzf

# List everything as JSON
passbolt list --json | jq '.[].name'

# Disambiguate multiple matches
passbolt copy git --pick

# Copy by UUID (exact match)
passbolt copy a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Export a password to pass
passbolt export "Production Database" Work/db/production

# Custom config file
passbolt -c ~/.config/passbolt/work.ini copy gmail
```

## How It Works

1. **Authentication**: The CLI authenticates with the Passbolt API using GPGAuth (default) or JWT (`auth_method = jwt`). With `auth_method = auto`, GPGAuth is tried first and JWT is used as a fallback. Authentication is deferred until the first API request. Optional server verification (`verify_server = true`) performs GPGAuth stage 0 before login.

2. **API Communication**: All communication uses the Passbolt REST API over HTTPS with `X-CSRF-Token` on authenticated requests. Collection endpoints such as `/resources.json` are paginated automatically.

3. **MFA**: If your account requires TOTP MFA, the CLI prompts for a code interactively or uses `mfa_totp_secret` from config for automation.

4. **Metadata**: v4 resources expose cleartext name/username/URI fields. v5 encrypted-metadata resources are decrypted locally using metadata private keys fetched from `/metadata/keys.json`, then normalized to the same fields used by search and list.

5. **Decryption**: Passwords are encrypted with your GPG public key. The CLI uses your private key to decrypt them locally.

6. **Clipboard**: Copy commands use system clipboard tools (`wl-copy`, `xclip`, `xsel`, or `pbcopy`). On Wayland, `wl-copy` stays running as a daemon; the CLI uses non-blocking subprocess handling so the terminal does not hang. After the configured timeout, the clipboard is cleared only if it still contains the copied secret.

## API Compatibility

| Feature | Status |
|---------|--------|
| GPGAuth login (`POST /auth/login.json`) | Supported |
| Optional server verification (stage 0) | Supported (`verify_server = true`) |
| CSRF token (`csrfToken` cookie + `X-CSRF-Token`) | Supported |
| JWT login (`POST /auth/jwt/login.json`) | Supported (`auth_method = jwt` or `auto`) |
| JWT refresh | Supported on session expiry |
| MFA TOTP (`POST /mfa/verify/totp.json`) | Supported (interactive or `mfa_totp_secret`) |
| Resource listing with pagination | Supported |
| v5 encrypted metadata decryption | Supported |
| Read secrets (`GET /secrets/resource/{id}.json`) | Supported |

For JWT authentication, set `user_id` in config to your Passbolt user UUID. For GPG authentication it is optional and auto-fetched from `/users/me.json`.

## Security Notes

- Your private key never leaves your machine
- Passwords and v5 metadata are decrypted locally using GPG
- API communication uses HTTPS; authenticated requests include CSRF tokens
- Clipboard contents are auto-cleared after a configurable timeout
- Clipboard clearing is content-aware and skipped if you have pasted something else
- Cached passwords in the TUI are overwritten when the app exits or the secret screen is closed
- Consider using a passphrase-protected GPG key
- `mfa_totp_secret` grants full API access without prompts — store it as carefully as your GPG passphrase
- Optional `verify_server = true` checks the server GPG key before login (recommended on first use with a new server)
- Store your configuration file securely with appropriate permissions:
  ```bash
  chmod 600 ~/.config/passbolt/config.ini
  ```

## Troubleshooting

### Authentication fails

- Verify your server URL is correct and accessible
- Ensure your private key file path is correct
- Check that your private key matches your Passbolt account
- If your key has a passphrase, make sure it's entered correctly
- Try `auth_method = gpg` explicitly if `auto` is attempting JWT unexpectedly
- For JWT-only servers, set `auth_method = jwt` and a valid `user_id`

### MFA prompts fail or block scripts

- Interactive terminal required unless `mfa_totp_secret` is set
- Ensure the secret is base32 (same as manual authenticator setup), not a one-time code
- Codes rotate every 30 seconds; retry if the clock on your machine is wrong (`timedatectl`)
- In CI, use `mfa_totp_secret` or a dedicated service account without MFA

### JWT authentication fails

- Confirm `user_id` matches your Passbolt account UUID
- Ensure `private_key_path` points to the key registered in Passbolt
- Check that the server has the JWT authentication plugin enabled
- CSRF cookie must be present: the CLI fetches `/auth/verify.json` before login automatically

### Empty names or "metadata" errors (v5)

- Log in with the browser extension first to receive metadata private keys
- Confirm you can see resource names in the web UI with the same account
- Shared metadata keys must be trusted/imported — contact your Passbolt admin if new keys were rotated
- Mixed v4/v5 resources are supported; only v5 entries need metadata decryption

### "Password not found" error

- Use `passbolt search` or `passbolt list` to find the exact name
- Password names are case-insensitive for matching
- Use `--pick` when multiple resources match the same query

### Terminal hangs after copy (Wayland)

- Ensure `wl-clipboard` is installed
- Older versions used blocking clipboard calls; current releases use non-blocking `Popen` with `wl-copy`

### GPG errors

- Ensure GPG is installed: `gpg --version`
- Verify your private key is valid: `gpg --list-secret-keys`
- Check key permissions: `ls -la ~/.passbolt/private_key.asc`

## Development

### Project Structure

```
passbolt-cli/
├── passbolt-cli.py       # Compatibility entry point (delegates to passbolt.cli)
├── passbolt/
│   ├── __init__.py       # Package initialization
│   ├── argv.py           # pass-style default command injection
│   ├── api_response.py   # API envelope parsing
│   ├── auth.py           # GPG/JWT authentication and MFA
│   ├── clipboard.py      # Clipboard copy/clear helpers
│   ├── client.py         # API client
│   ├── commands.py       # Command implementations
│   ├── config.py         # Configuration handling
│   ├── gpg.py            # GPG encrypt/decrypt helpers
│   ├── gpg_util.py       # GPGAuth token helpers
│   ├── http.py           # Authenticated HTTP with CSRF/pagination
│   ├── metadata.py       # v5 encrypted metadata decryption
│   ├── resources.py      # Resource name matching helpers
│   ├── secret.py         # Secret parsing and TOTP generation
│   ├── theme.py          # Wallust/pywal theme loader
│   └── tui.py            # Terminal user interface
├── completions/
│   └── passbolt.bash     # Bash shell completion
├── tests/                # Unit tests
├── pyproject.toml        # Project configuration and dependencies
├── config.ini.example    # Example configuration
└── README.md             # This file
```

### Running Tests

```bash
python -m unittest discover -s tests -v
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details

## Acknowledgments

- [Passbolt](https://www.passbolt.com/) - The password manager
- [password-store](https://www.passwordstore.org/) - Inspiration for the CLI design

## Disclaimer

This is an unofficial CLI tool for Passbolt. It is not affiliated with or endorsed by Passbolt or Passbolt SA.