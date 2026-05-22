#!/usr/bin/env python3
"""Debug authentication flow"""

import requests
from urllib.parse import urljoin
import gnupg
from pathlib import Path
from passbolt.config import load_config

config_path = Path("~/.config/passbolt/config.ini").expanduser()
config = load_config(config_path)

# Import key
gpg = gnupg.GPG()
import_result = gpg.import_keys(config.private_key)
fingerprint = import_result.fingerprints[0].replace("-", "").replace(" ", "").upper()

print(f"Using fingerprint: {fingerprint}")
print(f"Username: {config.username}")
print(f"Server: {config.server_url}\n")

session = requests.Session()

# Try verify endpoint
print("=== Step 1: Verify server ===")
verify_url = urljoin(config.server_url, "/auth/verify")
headers = {"X-GPGAuth-Version": "1.3.0"}
resp = session.get(verify_url, headers=headers)
print(f"Status: {resp.status_code}")
print("Headers:")
for k, v in resp.headers.items():
    if "gpgauth" in k.lower():
        print(f"  {k}: {v}")
print()

# Try login
print("=== Step 2: Request login challenge ===")
login_url = urljoin(config.server_url, "/auth/login")
headers = {
    "X-GPGAuth-Version": "1.3.0",
    "X-GPGAuth-User-Fingerprint": fingerprint,
}
resp = session.get(login_url, headers=headers)
print(f"Status: {resp.status_code}")
print("Headers:")
for k, v in resp.headers.items():
    if "gpgauth" in k.lower() or "auth" in k.lower():
        print(f"  {k}: {v}")

print("\nBody preview:")
try:
    print(resp.json())
except:
    print(resp.text[:500])
