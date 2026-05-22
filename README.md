# Passbolt CLI

A command-line interface for [Passbolt](https://www.passbolt.com/) password manager, designed to work similarly to [password-store](https://www.passwordstore.org/) (`pass`).

## Features

- **Copy passwords to clipboard** - Quickly copy passwords without leaving the terminal
- **Search passwords** - Find passwords by name, username, or URI
- **Interactive TUI** - Browse and search passwords in a terminal user interface
- **Export to pass** - Seamlessly migrate passwords to password-store
- **GPG authentication** - Uses your Passbolt recovery private key for authentication
- **INI configuration** - Simple configuration file format

## Requirements

- Python 3.8 or higher
- GPG (GnuPG)
- password-store (`pass`) - optional, only needed for export command

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

### Copy a password to clipboard

```bash
passbolt copy <password-name-or-uuid>
```

Example:
```bash
passbolt copy gmail
# Or use UUID for exact match
passbolt search gmail  # Get the UUID
passbolt copy a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

The password will be copied to your clipboard and automatically cleared after 45 seconds (configurable).

### Show a password

```bash
passbolt show <password-name-or-uuid>
```

Example:
```bash
passbolt show gmail
```

This will display the password on stdout in pass-compatible format.

### Search for passwords

```bash
passbolt search <query>
```

Example:
```bash
passbolt search google
```

This will display all passwords matching "google" with their details and UUIDs.

### Interactive TUI

Launch a terminal user interface for browsing and searching passwords.

```bash
passbolt tui
```

Keyboard shortcuts:
- `↑` / `↓` - Navigate entries
- `/` - Focus search box
- `Enter` / `Esc` - Move focus to results table (keeps filtered results)
- `c` - Copy password to clipboard
- `u` - Copy username to clipboard
- `o` - Copy URI to clipboard
- `s` - Show password on screen
- `q` - Quit

Search works in real time. Delete the search text to restore all results.

### Export to password-store

```bash
passbolt export <password-name-or-uuid> <pass-path>
```

Example:
```bash
passbolt export "My Gmail" Email/gmail
```

This will export the password to password-store at `Email/gmail`.

### Custom configuration file

You can specify a custom configuration file:

```bash
passbolt -c /path/to/config.ini copy gmail
```

## Examples

```bash
# Copy your GitHub password
passbolt copy github

# Show a password on stdout
passbolt show github

# Search for all AWS-related passwords
passbolt search aws

# Copy by UUID (useful when multiple matches or special characters in name)
passbolt copy a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Export a password to pass
passbolt export "Production Database" Work/db/production
```

## How It Works

1. **Authentication**: The CLI uses your GPG private key to authenticate with the Passbolt API, similar to how the browser extension works during account recovery.

2. **API Communication**: All communication with Passbolt happens through its REST API over HTTPS.

3. **Decryption**: Passwords are encrypted with your GPG public key. The CLI uses your private key to decrypt them locally.

4. **Clipboard**: The `copy` command uses the system clipboard to temporarily store passwords.

## Security Notes

- Your private key never leaves your machine
- Passwords are decrypted locally using GPG
- API communication uses HTTPS
- Consider using a passphrase-protected GPG key
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

### "Password not found" error

- Use the `search` command to find the exact name
- Password names are case-insensitive
- The CLI will suggest alternatives if multiple matches are found

### GPG errors

- Ensure GPG is installed: `gpg --version`
- Verify your private key is valid: `gpg --list-secret-keys`
- Check key permissions: `ls -la ~/.passbolt/private_key.asc`

## Development

### Project Structure

```
passbolt-cli/
├── passbolt-cli.py       # Main entry point
├── passbolt/
│   ├── __init__.py       # Package initialization
│   ├── auth.py           # GPG authentication
│   ├── client.py         # API client
│   ├── commands.py       # Command implementations
│   ├── config.py         # Configuration handling
│   └── tui.py            # Terminal user interface
├── pyproject.toml        # Project configuration and dependencies
├── config.ini.example   # Example configuration
└── README.md            # This file
```

### Running Tests

```bash
# TODO: Add tests
python -m pytest
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
