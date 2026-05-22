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

Edit `~/.config/passbolt/config.ini`:

```ini
[passbolt]
server_url = https://passbolt.example.com
username = user@example.com
private_key_path = ~/.passbolt/private_key.asc
```

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

### Interactive TUI
```bash
passbolt tui
```

Keyboard shortcuts:
- `↑` / `↓` - Navigate entries
- `/` - Focus search box
- `Enter` / `Esc` - Move focus to results table
- `c` - Copy password to clipboard
- `u` - Copy username to clipboard
- `o` - Copy URI to clipboard
- `s` - Show password on screen
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

### Enable debug output
```bash
# Add -v or --verbose flag (if implemented)
passbolt -v search test
```

## Tips

1. **Password names are case-insensitive** - `gmail`, `Gmail`, and `GMAIL` all work
2. **Partial matching** - Searching for "git" will find "github", "gitlab", etc.
3. **Use quotes for names with spaces** - `passbolt copy "My Password"`
4. **Clipboard is temporary** - The password is only copied, not displayed
5. **Export preserves metadata** - Username and URL are included in pass exports

## Security Best Practices

- Keep your private key secure: `chmod 600 ~/.passbolt/private_key.asc`
- Don't store your passphrase in config - enter it when prompted
- Use a strong passphrase for your GPG key
- Regularly rotate your passwords
- Clear clipboard after use (automatic with most clipboard managers)
