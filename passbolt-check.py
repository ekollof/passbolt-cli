#!/usr/bin/env python3
"""
Check Passbolt CLI configuration
"""

import sys
from pathlib import Path

from passbolt.config import load_config
from passbolt.auth import PassboltAuth


def main():
    """Check configuration and display detected settings"""
    config_path = Path('~/.config/passbolt/config.ini').expanduser()
    
    if not config_path.exists():
        print(f"❌ Configuration file not found at {config_path}")
        print("Create one using: cp config.ini.example ~/.config/passbolt/config.ini")
        sys.exit(1)
    
    print("Checking Passbolt CLI configuration...\n")
    
    try:
        config = load_config(config_path)
        print(f"✓ Configuration loaded successfully")
        print(f"  Server URL: {config.server_url}")
        print(f"  Username: {config.username}")
        print(f"  Private key: {config.private_key_path}")
        
        if config.private_key_path.exists():
            print(f"  ✓ Private key file exists")
        else:
            print(f"  ❌ Private key file not found!")
            sys.exit(1)
        
        print()
        print("Importing GPG key and detecting fingerprint...")
        
        auth = PassboltAuth(config)
        print(f"✓ GPG key imported successfully")
        print(f"  Detected fingerprint: {auth.fingerprint}")
        print()
        print("Next steps:")
        print(f"1. Log into Passbolt at {config.server_url}")
        print(f"2. Go to Profile > Keys")
        print(f"3. Verify this fingerprint matches: {auth.fingerprint}")
        print(f"4. Verify username matches: {config.username}")
        print()
        print("If everything matches, try: ./passbolt-cli.py search test")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
