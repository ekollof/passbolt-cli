"""Low-level GPG operations for Passbolt authentication and decryption."""

from __future__ import annotations

import gnupg

from passbolt.gpg_util import (
    check_auth_token_format,
    decode_gpgauth_header_value,
    make_gpgauth_token,
    normalize_fingerprint,
)


class GPGHelper:
    """Thin wrapper around python-gnupg for Passbolt operations."""

    def __init__(
        self,
        private_key: str,
        passphrase: str = "",
        user_fingerprint: str | None = None,
    ) -> None:
        self.gpg = gnupg.GPG()
        self.passphrase = passphrase
        import_result = self.gpg.import_keys(private_key)
        if not import_result.fingerprints:
            raise ValueError("Failed to import private key")

        if user_fingerprint:
            clean = normalize_fingerprint(user_fingerprint)
            if clean not in {
                normalize_fingerprint(fp) for fp in import_result.fingerprints
            }:
                raise ValueError(
                    f"Configured user_fingerprint does not match imported key: {user_fingerprint}"
                )
            self.fingerprint = clean
        else:
            self.fingerprint = normalize_fingerprint(import_result.fingerprints[0])

    def import_key(self, key_data: str) -> str:
        """Import an armored key and return its fingerprint."""
        import_result = self.gpg.import_keys(key_data)
        if not import_result.fingerprints:
            raise ValueError("Failed to import key")
        return normalize_fingerprint(import_result.fingerprints[0])

    def decrypt(self, encrypted_data: str, passphrase: str | None = None) -> str:
        """Decrypt armored ciphertext."""
        decrypted = self.gpg.decrypt(
            encrypted_data,
            passphrase=passphrase if passphrase is not None else self.passphrase,
        )
        if not decrypted.ok:
            raise ValueError(f"Failed to decrypt data: {decrypted.status}")
        return str(decrypted)

    def encrypt(self, data: str, recipient_fingerprint: str) -> str:
        """Encrypt data for a recipient."""
        encrypted = self.gpg.encrypt(
            data,
            recipient_fingerprint,
            always_trust=True,
        )
        if not encrypted.ok:
            raise ValueError(f"Failed to encrypt data: {encrypted.status}")
        return str(encrypted)

    def sign_and_encrypt(self, data: str, recipient_fingerprint: str) -> str:
        """Sign with the user key and encrypt for a recipient (JWT challenge)."""
        encrypted = self.gpg.encrypt(
            data,
            recipient_fingerprint,
            sign=self.fingerprint,
            passphrase=self.passphrase,
            always_trust=True,
        )
        if not encrypted.ok:
            raise ValueError(f"Failed to sign and encrypt data: {encrypted.status}")
        return str(encrypted)

    def fingerprint_from_armored(self, armored_key: str) -> str:
        """Return the fingerprint of an armored public key."""
        imported = self.gpg.import_keys(armored_key)
        if not imported.fingerprints:
            raise ValueError("Failed to import armored key")
        return normalize_fingerprint(imported.fingerprints[0])