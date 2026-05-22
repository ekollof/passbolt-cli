"""Configuration handling for Passbolt CLI"""

from __future__ import annotations

import configparser
import subprocess
from pathlib import Path
from typing import Any


class PassboltConfig:
    """Passbolt configuration wrapper"""

    def __init__(self, config_dict: dict[str, Any]) -> None:
        self.server_url: str | None = config_dict.get("server_url")
        self.username: str | None = config_dict.get("username")
        private_key_path_str: str | None = config_dict.get("private_key_path")
        self.user_fingerprint: str | None = config_dict.get("user_fingerprint")
        self._passphrase_config: str = config_dict.get("passphrase", "")
        self.clipboard_timeout: int = int(config_dict.get("clipboard_timeout", "45"))

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


def load_config(config_path: Path) -> PassboltConfig:
    """Load configuration from INI file"""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    parser = configparser.ConfigParser()
    parser.read(config_path)

    if "passbolt" not in parser:
        raise ValueError("Configuration file must contain [passbolt] section")

    config_dict = dict(parser["passbolt"])
    return PassboltConfig(config_dict)
