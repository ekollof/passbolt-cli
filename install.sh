#!/bin/bash
# Quick installation script for Passbolt CLI
# Prefers uv (https://github.com/astral-sh/uv), falls back to pipx

set -e

echo "===================================="
echo "Passbolt CLI Installation"
echo "===================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || {
    echo "Error: Python 3 is required but not found"
    exit 1
}

# Check GPG
echo "Checking GPG..."
gpg --version > /dev/null || {
    echo "Error: GPG is required but not found"
    echo "Install it with: sudo apt install gnupg (Debian/Ubuntu) or brew install gnupg (macOS)"
    exit 1
}

# Determine installer: prefer uv, then pipx
INSTALLER=""
if command -v uv >/dev/null 2>&1; then
    INSTALLER="uv"
    echo "Found uv — using uv tool install"
elif command -v pipx >/dev/null 2>&1; then
    INSTALLER="pipx"
    echo "Found pipx — using pipx install"
else
    echo ""
    echo "Error: Neither uv nor pipx was found."
    echo ""
    echo "Please install one of them first:"
    echo ""
    echo "  uv (recommended):"
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "    # or: brew install uv"
    echo "    # or: pipx install uv"
    echo ""
    echo "  pipx:"
    echo "    python3 -m pip install --user pipx"
    echo "    pipx ensurepath"
    echo ""
    exit 1
fi

# Install the tool
echo ""
echo "Installing Passbolt CLI..."
if [ "$INSTALLER" = "uv" ]; then
    uv tool install -e .
elif [ "$INSTALLER" = "pipx" ]; then
    pipx install -e .
fi

# Make CLI executable (for direct invocation without install)
if [ -f passbolt-cli.py ]; then
    echo "Making CLI executable..."
    chmod +x passbolt-cli.py
fi

# Create config directory
echo "Creating configuration directory..."
mkdir -p ~/.config/passbolt

# Copy example config if it doesn't exist
if [ ! -f ~/.config/passbolt/config.ini ]; then
    echo "Copying example configuration..."
    cp config.ini.example ~/.config/passbolt/config.ini
    chmod 600 ~/.config/passbolt/config.ini
    echo "⚠️  Please edit ~/.config/passbolt/config.ini with your settings"
else
    echo "Configuration file already exists at ~/.config/passbolt/config.ini"
fi

echo ""
echo "===================================="
echo "Installation complete!"
echo "===================================="
echo ""
echo "Next steps:"
echo "1. Edit your configuration: nano ~/.config/passbolt/config.ini"
echo "2. Add your Passbolt server URL"
echo "3. Add your Passbolt username (email address)"
echo "4. Save your GPG private key to ~/.passbolt/private_key.asc"
echo "5. Run: passbolt search test"
echo ""
echo "For help, run: passbolt --help"
