"""Configuration handling for Passbolt CLI"""

from __future__ import annotations

import configparser
import os
import subprocess
from pathlib import Path
from typing import Any


def _parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def default_config_path() -> Path:
    """Return the default configuration file path."""
    env_path = os.environ.get("PASSBOLT_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    return Path("~/.config/passbolt/config.ini").expanduser()


class PassboltConfig:
    """Passbolt configuration wrapper"""

    def __init__(self, config_dict: dict[str, Any]) -> None:
        self.server_url: str | None = config_dict.get("server_url")
        self.username: str | None = config_dict.get("username")
        private_key_path_str: str | None = config_dict.get("private_key_path")
        self.user_fingerprint: str | None = config_dict.get("user_fingerprint")
        self.user_id: str | None = config_dict.get("user_id")
        self.auth_method: str = config_dict.get("auth_method", "auto").lower()
        self.verify_server: bool = _parse_bool(config_dict.get("verify_server", "false"))
        self.mfa_totp_secret: str | None = config_dict.get("mfa_totp_secret") or None
        self._passphrase_config: str = config_dict.get("passphrase", "")
        self.clipboard_timeout: int = int(config_dict.get("clipboard_timeout", "45"))

        if self.auth_method not in {"auto", "gpg", "jwt"}:
            raise ValueError("auth_method must be one of: auto, gpg, jwt")
        if self.auth_method == "jwt" and not self.user_id:
            raise ValueError("user_id is required when auth_method is jwt")

        # Validate required fields
        if not self.server_url:
            raise ValueError("server_url is required in configuration")
        if not self.username:
            raise ValueError("username is required in configuration")
        if not private_key_path_str:
            raise ValueError("private_key_path is required in configuration")

        # Expand paths
        self.private_key_path: Path = Path(private_key_path_str).expanduser()

        # Ensure server URL doesn't end with slash
        self.server_url = self.server_url.rstrip("/")

    @property
    def passphrase(self) -> str:
        """Get passphrase, executing command if needed"""
        if self._passphrase_config.startswith("exec:"):
            # Extract and execute command
            command = self._passphrase_config[5:].strip()
            try:
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    raise ValueError(f"Passphrase command failed: {result.stderr}")
                # Return stdout, stripping trailing newline
                return result.stdout.rstrip("\n")
            except subprocess.TimeoutExpired:
                raise ValueError("Passphrase command timed out")
            except Exception as e:
                raise ValueError(f"Failed to execute passphrase command: {e}")
        return self._passphrase_config

    @property
    def private_key(self) -> str:
        """Load and return the private key"""
        if not self.private_key_path.exists():
            raise FileNotFoundError(f"Private key not found at {self.private_key_path}")
        return self.private_key_path.read_text()


def load_config(config_path: Path | None = None) -> PassboltConfig:
    """Load configuration from INI file"""
    path = config_path or default_config_path()
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    parser = configparser.ConfigParser()
    parser.read(path)

    if "passbolt" not in parser:
        raise ValueError("Configuration file must contain [passbolt] section")

    config_dict = dict(parser["passbolt"])
    return PassboltConfig(config_dict)