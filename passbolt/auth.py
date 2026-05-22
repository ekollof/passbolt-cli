"""Authentication handling for Passbolt API"""

from __future__ import annotations

import gnupg
import json
import requests
from urllib.parse import urljoin, unquote_plus

from passbolt.config import PassboltConfig


class PassboltAuth:
    """Handle Passbolt authentication using GPG keys"""

    def __init__(self, config: PassboltConfig) -> None:
        self.config: PassboltConfig = config
        self.gpg: gnupg.GPG = gnupg.GPG()
        self._import_private_key()

    def _import_private_key(self) -> None:
        """Import the private key into GPG"""
        private_key = self.config.private_key
        import_result = self.gpg.import_keys(private_key)

        if not import_result.fingerprints:
            raise ValueError("Failed to import private key")

        self.fingerprint = import_result.fingerprints[0]

    def decrypt_secret(self, encrypted_data: str) -> str:
        """Decrypt an encrypted secret using GPG"""
        passphrase = self.config.passphrase

        decrypted = self.gpg.decrypt(encrypted_data, passphrase=passphrase)

        if not decrypted.ok:
            raise ValueError(f"Failed to decrypt secret: {decrypted.status}")

        return str(decrypted)

    def encrypt_data(self, data: str, recipient_fingerprint: str) -> str:
        """Encrypt data for a specific recipient"""
        encrypted = self.gpg.encrypt(data, recipient_fingerprint, always_trust=True)

        if not encrypted.ok:
            raise ValueError(f"Failed to encrypt data: {encrypted.status}")

        return str(encrypted)

    def get_auth_token(self) -> requests.Session:
        """
        Authenticate with Passbolt API using GPG Auth protocol v1.3.0

        Implements the official GPG Auth protocol as documented at:
        https://www.passbolt.com/docs/development/authentication/

        Returns authenticated session with cookies
        """
        session = requests.Session()

        try:
            # Remove hyphens and ensure uppercase for fingerprint
            clean_fingerprint = (
                self.fingerprint.replace("-", "").replace(" ", "").upper()
            )

            # Stage 1: Request login challenge (POST to /auth/login.json)
            server_url = self.config.server_url
            assert server_url is not None
            login_url = urljoin(server_url, "/auth/login.json")

            # Request payload as per official documentation
            payload = {
                "data": {
                    "gpg_auth": {
                        "keyid": clean_fingerprint,
                    }
                }
            }

            response = session.post(
                login_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            # Check for errors in response headers
            if "X-GPGAuth-Error" in response.headers:
                error_msg = response.headers["X-GPGAuth-Error"]
                debug_msg = response.headers.get("X-GPGAuth-Debug", "")
                raise ValueError(f"GPGAuth Error: {error_msg}. Debug: {debug_msg}")

            # Check for encrypted token in response headers
            if "X-GPGAuth-User-Auth-Token" not in response.headers:
                try:
                    body = response.json()
                    body_msg = json.dumps(body, indent=2)
                except Exception:
                    body_msg = response.text[:500] if response.text else "empty"

                raise ValueError(
                    "No encrypted token received in X-GPGAuth-User-Auth-Token header.\n"
                    f"Status: {response.status_code}\n"
                    f"Body: {body_msg}"
                )

            # Get the encrypted token from header and URL-decode it
            encrypted_token = response.headers["X-GPGAuth-User-Auth-Token"]
            # Replace \+ with + first (backslash-escaped plus signs)
            encrypted_token = encrypted_token.replace("\\+", "+")
            # Then URL-decode (+ becomes space, %0A becomes newline, etc.)
            encrypted_token = unquote_plus(encrypted_token)

            # Stage 2: Decrypt the challenge token
            passphrase = self.config.passphrase
            decrypted = self.gpg.decrypt(encrypted_token, passphrase=passphrase)

            if not decrypted.ok:
                raise ValueError(f"Failed to decrypt auth token: {decrypted.status}")

            decrypted_token = str(decrypted).strip()

            # Verify the token format (should be gpgauthv1.3.0|36|UUID|gpgauthv1.3.0)
            if not decrypted_token.startswith("gpgauthv1.3.0|"):
                raise ValueError(f"Invalid decrypted token format: {decrypted_token}")

            # Stage 3: Send decrypted token back to complete authentication
            verify_payload = {
                "data": {
                    "gpg_auth": {
                        "keyid": clean_fingerprint,
                        "user_token_result": decrypted_token,
                    }
                }
            }

            final_response = session.post(
                login_url,
                json=verify_payload,
                headers={"Content-Type": "application/json"},
            )

            # Check for errors in final response
            if "X-GPGAuth-Error" in final_response.headers:
                error_msg = final_response.headers["X-GPGAuth-Error"]
                debug_msg = final_response.headers.get("X-GPGAuth-Debug", "")
                raise ValueError(
                    f"GPGAuth Error in final step: {error_msg}. Debug: {debug_msg}"
                )

            # Check authentication status
            authenticated = final_response.headers.get(
                "X-GPGAuth-Authenticated", "false"
            )
            if authenticated.lower() != "true":
                try:
                    body = final_response.json()
                    body_msg = json.dumps(body, indent=2)
                except Exception:
                    body_msg = (
                        final_response.text[:500] if final_response.text else "empty"
                    )

                raise ValueError(
                    "Authentication not confirmed (X-GPGAuth-Authenticated != true).\n"
                    f"Status: {final_response.status_code}\n"
                    f"Body: {body_msg}"
                )

            # Check if we have session cookies
            if not session.cookies:
                raise ValueError("No session cookies received after authentication")

            return session

        except requests.exceptions.RequestException as e:
            raise Exception(f"Authentication request failed: {e}")
        except Exception as e:
            error_msg = str(e)
            if "No user associated with this key" in error_msg:
                raise Exception(
                    f"GPG authentication failed: {e}\n\n"
                    f"Your GPG key (fingerprint: {self.fingerprint}) is not registered in Passbolt.\n"
                    f"Please ensure:\n"
                    f"1. You're using the correct private key\n"
                    f"2. The key is registered in your Passbolt account (Profile > Keys)\n"
                    f"3. The username '{self.config.username}' matches your Passbolt account"
                )
            raise Exception(f"GPG authentication failed: {e}")
