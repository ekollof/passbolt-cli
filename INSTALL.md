# Installation Guide

## Quick Start with uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager and runtime. It installs tools in isolated environments without dependency conflicts.

### 1. Install uv (if not already installed)

```bash
# Using the official installer
curl -LsSf https://astral.sh/uv/install.sh | sh

# On macOS with Homebrew
brew install uv

# Or using pipx
pipx install uv
```

After installation, restart your shell or run:
```bash
source ~/.bashrc  # or ~/.zshrc
```

### 2. Install passbolt-cli

#### From local directory:
```bash
cd /path/to/passbolt-cli
uv tool install -e .
```

#### From git repository:
```bash
uv tool install git+https://github.com/ekollof/passbolt-cli.git
```

### 3. Verify installation

```bash
passbolt --help
```

## Alternative: Using pipx

If you prefer [pipx](https://pipx.pypa.io/) over uv:

```bash
# Install pipx (if not already installed)
python3 -m pip install --user pipx
pipx ensurepath

# Install passbolt-cli
pipx install -e .          # From local directory
# or
pipx install git+https://github.com/ekollof/passbolt-cli.git
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
# With uv
uv tool upgrade passbolt-cli

# Or reinstall from local directory
cd /path/to/passbolt-cli
git pull
uv tool install --force -e .
```

```bash
# With pipx
pipx upgrade passbolt-cli

# Or reinstall from local directory
cd /path/to/passbolt-cli
git pull
pipx install --force -e .
```

## Uninstalling

```bash
# With uv
uv tool uninstall passbolt-cli

# With pipx
pipx uninstall passbolt-cli
```

## Alternative: Install with pip

If you prefer pip over uv or pipx:

```bash
# Install for current user
pip install --user .

# Or system-wide (requires sudo)
sudo pip install .
```

Note: Using uv or pipx is recommended to avoid dependency conflicts with other Python packages.

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

If using pipx, run `pipx ensurepath` and restart your shell.
If using uv, ensure `~/.local/bin` is in your PATH.

### Permission errors

Use `uv` or `pipx` instead of `sudo pip`.

### Dependency conflicts

This is why uv or pipx is recommended — they create isolated environments. If using pip, consider using a virtual environment:

```bash
python3 -m venv ~/.local/venvs/passbolt
source ~/.local/venvs/passbolt/bin/activate
pip install -e .
```
