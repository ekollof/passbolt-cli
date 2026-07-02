# Passbolt CLI - Quick Reference

## Installation

```bash
# Using uv (recommended)
uv tool install -e .

# Using pipx
pipx install -e .

# Or use the install script (auto-detects uv or pipx)
./install.sh
```

## Configuration

Copy and edit `~/.config/passbolt/config.ini` (see `config.ini.example` for all options):

```ini
[passbolt]
server_url = https://passbolt.example.com
username = user@example.com
private_key_path = ~/.passbolt/private_key.asc
passphrase = exec:pass show passbolt/gpg-passphrase
```

### Optional (API / auth)

```ini
# JWT auth or auto-fallback (required for auth_method = jwt)
# user_id = 8bb80df5-700c-48ce-b568-85a60fc3c8f2

# auto (default) | gpg | jwt
# auth_method = auto

# Promptless MFA for scripts (base32 secret, not a 6-digit code)
# mfa_totp_secret = JBSWY3DPEHPK3PXP
```

Most users only need the three required fields. Use `auth_method = jwt` + `user_id` if GPGAuth is disabled on your server. Set `mfa_totp_secret` only for non-interactive MFA.

## Common Commands

### Copy password to clipboard
```bash
passbolt copy <name>

# Examples:
passbolt copy gmail
passbolt copy "My GitHub Account"
```

### Search for passwords
```bash
passbolt search <query>

# Examples:
passbolt search google
passbolt search aws
passbolt search database
```

### Generate a TOTP code
```bash
passbolt totp <name>

# Examples:
passbolt totp github
```

### Interactive TUI
```bash
passbolt tui
```

Keyboard shortcuts:
- `↑` / `↓` - Navigate entries
- `/` - Focus search box
- `Tab` - Switch between search and results
- `Enter` / `Esc` - Focus results (Esc also clears search text)
- `c` - Copy password to clipboard
- `t` - Copy TOTP code to clipboard
- `u` - Copy username to clipboard
- `o` - Copy URI to clipboard
- `s` - Show password on screen
- `r` - Refresh from server
- `q` - Quit

### Export to password-store
```bash
passbolt export <passbolt-name> <pass-path>

# Examples:
passbolt export gmail Email/gmail
passbolt export "Production DB" Work/databases/prod
```

### Use custom config
```bash
passbolt -c /path/to/config.ini <command>

# Example:
passbolt -c ~/work/passbolt.ini search project
```

## Workflow Examples

### Daily usage
```bash
# Find a password
passbolt search github

# Copy it
passbolt copy github
```

### Migration to pass
```bash
# Search for all work passwords
passbolt search work

# Export them one by one
passbolt export "Work Email" Work/email
passbolt export "Work VPN" Work/vpn
passbolt export "Work Database" Work/database
```

### Batch operations
```bash
# List all passwords matching a pattern
passbolt search aws

# Copy each one as needed
passbolt copy "AWS Production"
passbolt copy "AWS Staging"
```

## Troubleshooting

### Check configuration
```bash
cat ~/.config/passbolt/config.ini
```

### Verify GPG key
```bash
gpg --import < ~/.passbolt/private_key.asc
gpg --list-secret-keys
```

### Test connection
```bash
curl -I https://your-passbolt-server.com
```

### Authentication / MFA / v5 metadata

| Symptom | Fix |
|---------|-----|
| Auth fails with JWT errors | Set `user_id` and `auth_method = jwt` |
| MFA prompt in scripts | Add `mfa_totp_secret` or use a non-MFA account |
| Empty resource names (v5) | Log in via browser extension first to provision metadata keys |
| GPG works in browser, not CLI | Check `private_key_path` and `user_fingerprint` |

See README.md for full troubleshooting and API compatibility details.

## Tips

1. **Password names are case-insensitive** - `gmail`, `Gmail`, and `GMAIL` all work
2. **Partial matching** - Searching for "git" will find "github", "gitlab", etc.
3. **Use quotes for names with spaces** - `passbolt copy "My Password"`
4. **pass-style default** - `passbolt gmail` copies, like `pass -c gmail`
5. **Clipboard auto-clears** - Default 45s; content-aware (won't wipe unrelated clipboard data)
6. **Export preserves metadata** - Username and URL are included in pass exports (v5 metadata decrypted automatically)

## Security Best Practices

- Keep your private key secure: `chmod 600 ~/.passbolt/private_key.asc`
- Don't store your passphrase in config - enter it when prompted
- Use a strong passphrase for your GPG key
- Regularly rotate your passwords
- Clear clipboard after use (automatic with most clipboard managers)
