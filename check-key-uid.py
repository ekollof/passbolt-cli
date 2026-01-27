#!/usr/bin/env python3
"""Check GPG key UID"""

import gnupg
from pathlib import Path
from passbolt.config import load_config

config_path = Path('~/.config/passbolt/config.ini').expanduser()
config = load_config(config_path)

gpg = gnupg.GPG()
import_result = gpg.import_keys(config.private_key)
fingerprint = import_result.fingerprints[0]

# Get key details
keys = gpg.list_keys(keys=fingerprint)
if keys:
    key = keys[0]
    print(f"GPG Key Details:")
    print(f"  Fingerprint: {key['fingerprint']}")
    print(f"  Key ID: {key['keyid']}")
    print(f"  UIDs: {key['uids']}")
    print()
    print(f"Configured username: {config.username}")
    print()
    
    # Check if any UID matches username
    email_in_uid = any(config.username.lower() in uid.lower() for uid in key['uids'])
    if email_in_uid:
        print("✓ Username found in GPG key UID")
    else:
        print("⚠ Username NOT found in GPG key UID")
        print("  This might cause authentication issues")
