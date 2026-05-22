# Passbolt CLI - Quick Reference

## Installation

```bash
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
./passbolt-cli.py copy <name>

# Examples:
./passbolt-cli.py copy gmail
./passbolt-cli.py copy "My GitHub Account"
```

### Search for passwords
```bash
./passbolt-cli.py search <query>

# Examples:
./passbolt-cli.py search google
./passbolt-cli.py search aws
./passbolt-cli.py search database
```

### Interactive TUI
```bash
./passbolt-cli.py tui
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
./passbolt-cli.py export <passbolt-name> <pass-path>

# Examples:
./passbolt-cli.py export gmail Email/gmail
./passbolt-cli.py export "Production DB" Work/databases/prod
```

### Use custom config
```bash
./passbolt-cli.py -c /path/to/config.ini <command>

# Example:
./passbolt-cli.py -c ~/work/passbolt.ini search project
```

## Workflow Examples

### Daily usage
```bash
# Find a password
./passbolt-cli.py search github

# Copy it
./passbolt-cli.py copy github
```

### Migration to pass
```bash
# Search for all work passwords
./passbolt-cli.py search work

# Export them one by one
./passbolt-cli.py export "Work Email" Work/email
./passbolt-cli.py export "Work VPN" Work/vpn
./passbolt-cli.py export "Work Database" Work/database
```

### Batch operations
```bash
# List all passwords matching a pattern
./passbolt-cli.py search aws

# Copy each one as needed
./passbolt-cli.py copy "AWS Production"
./passbolt-cli.py copy "AWS Staging"
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
./passbolt-cli.py -v search test
```

## Tips

1. **Password names are case-insensitive** - `gmail`, `Gmail`, and `GMAIL` all work
2. **Partial matching** - Searching for "git" will find "github", "gitlab", etc.
3. **Use quotes for names with spaces** - `./passbolt-cli.py copy "My Password"`
4. **Clipboard is temporary** - The password is only copied, not displayed
5. **Export preserves metadata** - Username and URL are included in pass exports

## Security Best Practices

- Keep your private key secure: `chmod 600 ~/.passbolt/private_key.asc`
- Don't store your passphrase in config - enter it when prompted
- Use a strong passphrase for your GPG key
- Regularly rotate your passwords
- Clear clipboard after use (automatic with most clipboard managers)
