#!/bin/bash
# Quick installation script for Passbolt CLI

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

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Make CLI executable
echo "Making CLI executable..."
chmod +x passbolt-cli.py

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
echo "5. Run: ./passbolt-cli.py search test"
echo ""
echo "For help, run: ./passbolt-cli.py --help"
