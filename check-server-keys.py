#!/usr/bin/env python3
"""Check what Passbolt knows about the user's GPG key"""

import requests
from urllib.parse import urljoin
from passbolt.config import load_config
from pathlib import Path

config_path = Path("~/.config/passbolt/config.ini").expanduser()
config = load_config(config_path)

print(f"Checking Passbolt server for user: {config.username}\n")

# Try to get the server's public key
pubkey_url = urljoin(config.server_url, "/auth/verify.json")
try:
    resp = requests.get(pubkey_url)
    print(f"Server GPG key endpoint: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        if "body" in data and "fingerprint" in data["body"]:
            print(f"  Server fingerprint: {data['body']['fingerprint']}")
except Exception as e:
    print(f"  Error: {e}")

print()

# Try to get user's public key from server
# Passbolt might have an endpoint like /users/<email>/gpgkey or similar
user_key_urls = [
    f"/users.json?filter[search]={config.username}",
    "/gpgkeys.json",
]

for url_path in user_key_urls:
    url = urljoin(config.server_url, url_path)
    print(f"Trying: {url}")
    try:
        resp = requests.get(url)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"  Response: {str(data)[:200]}...")
            except:
                print(f"  Body: {resp.text[:200]}...")
    except Exception as e:
        print(f"  Error: {e}")
    print()

print("\n" + "=" * 60)
print("IMPORTANT: Check in Passbolt web interface:")
print("=" * 60)
print("1. Go to Profile → Keys")
print("2. Is the private key SAVED (not just displayed)?")
print("3. Try removing and re-adding the GPG key")
print("4. Check if there's a 'primary' or 'active' key setting")
print("5. Verify you completed the key setup wizard")
