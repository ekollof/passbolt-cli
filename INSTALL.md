# Installation Guide

## Quick Start with pipx (Recommended)

pipx installs Python applications in isolated environments, preventing dependency conflicts.

### 1. Install pipx (if not already installed)

```bash
# On Debian/Ubuntu
sudo apt install pipx
pipx ensurepath

# On Fedora
sudo dnf install pipx
pipx ensurepath

# On macOS
brew install pipx
pipx ensurepath

# Using pip
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

After installation, restart your shell or run:
```bash
source ~/.bashrc  # or ~/.zshrc
```

### 2. Install passbolt-cli

#### From local directory:
```bash
cd /path/to/passbolt-cli
pipx install .
```

#### From git repository:
```bash
pipx install git+https://github.com/ekollof/passbolt-cli.git
```

### 3. Verify installation

```bash
passbolt --help
```

## Configuration

1. Create the configuration directory:
```bash
mkdir -p ~/.config/passbolt
```

2. Create configuration file:
```bash
cat > ~/.config/passbolt/config.ini << 'EOF'
[passbolt]
server_url = https://your-passbolt-server.com
username = your.email@example.com
private_key_path = ~/.passbolt/private_key.asc
passphrase = exec:pass show passbolt/gpg-passphrase
clipboard_timeout = 45
EOF
```

3. Set secure permissions:
```bash
chmod 600 ~/.config/passbolt/config.ini
```

## First Use

1. Test authentication:
```bash
passbolt search test
```

2. Copy a password:
```bash
passbolt copy <password-name>
```

3. Show password on stdout:
```bash
passbolt show <password-name>
```

## Updating

To update to the latest version:

```bash
# From git
pipx upgrade passbolt-cli

# Or reinstall from local directory
cd /path/to/passbolt-cli
git pull
pipx install --force .
```

## Uninstalling

```bash
pipx uninstall passbolt-cli
```

## Alternative: Install with pip

If you prefer pip over pipx:

```bash
# Install for current user
pip install --user .

# Or system-wide (requires sudo)
sudo pip install .
```

Note: Using pipx is recommended to avoid dependency conflicts with other Python packages.

## System Requirements

- **Python**: 3.8 or higher
- **GPG**: For key decryption
- **Clipboard tools**: 
  - Linux/X11: `xclip` or `xsel`
  - Linux/Wayland: `wl-clipboard`
  - macOS: Built-in `pbcopy`

### Installing clipboard tools

```bash
# Debian/Ubuntu
sudo apt install xclip

# Fedora
sudo dnf install xclip

# macOS - already included
```

## Troubleshooting

### Command not found after installation

Run `pipx ensurepath` and restart your shell.

### Permission errors

Use `pipx` instead of `sudo pipx`.

### Dependency conflicts

This is why pipx is recommended - it creates isolated environments. If using pip, consider using a virtual environment:

```bash
python3 -m venv ~/.local/venvs/passbolt
source ~/.local/venvs/passbolt/bin/activate
pip install .
```
