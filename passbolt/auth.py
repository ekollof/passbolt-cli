"""Authentication handling for Passbolt API."""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin

import requests

from passbolt.api_response import APIError, ensure_success, extract_header
from passbolt.config import PassboltConfig
from passbolt.gpg import GPGHelper
from passbolt.gpg_util import (
    check_auth_token_format,
    decode_gpgauth_header_value,
    make_gpgauth_token,
)
from passbolt.http import AuthState, PassboltHTTPClient
from passbolt.secret import generate_totp


class PassboltAuth:
    """Handle Passbolt authentication using GPG and/or JWT."""

    def __init__(self, config: PassboltConfig) -> None:
        self.config = config
        self.gpg = GPGHelper(
            config.private_key,
            passphrase=config.passphrase,
            user_fingerprint=config.user_fingerprint,
        )

    def decrypt_secret(self, encrypted_data: str) -> str:
        """Decrypt an encrypted secret using the user's GPG key."""
        return self.gpg.decrypt(encrypted_data)

    def encrypt_data(self, data: str, recipient_fingerprint: str) -> str:
        """Encrypt data for a specific recipient."""
        return self.gpg.encrypt(data, recipient_fingerprint)

    def authenticate(self) -> AuthState:
        """Authenticate and return a ready-to-use auth state."""
        session = requests.Session()
        auth_state = AuthState(session=session, auth_method=self.config.auth_method)
        auth_state.reauthenticate = lambda: self._login(auth_state)
        auth_state.handle_mfa = lambda challenge: self._handle_mfa(auth_state, challenge)

        self._prime_csrf(session)
        if self.config.verify_server:
            self._verify_server(session)

        self._login(auth_state)
        self._finalize_session(auth_state)
        return auth_state

    def _prime_csrf(self, session: requests.Session) -> None:
        """Fetch the server key and initial CSRF cookie."""
        server_url = self.config.server_url
        assert server_url is not None
        response = session.get(
            urljoin(server_url, "/auth/verify.json"),
            headers={"Accept": "application/json"},
            timeout=30,
        )
        response.raise_for_status()

    def _verify_server(self, session: requests.Session) -> None:
        """Optional GPGAuth stage 0 server verification."""
        server_url = self.config.server_url
        assert server_url is not None
        verify_url = urljoin(server_url, "/auth/verify.json")
        response = session.get(verify_url, headers={"Accept": "application/json"}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        body = payload.get("body", payload)
        server_key = body["keydata"]

        token = make_gpgauth_token()
        encrypted_token = self.gpg.encrypt(token, self.gpg.fingerprint_from_armored(server_key))

        verify_payload = {
            "data": {
                "gpg_auth": {
                    "keyid": self.gpg.fingerprint,
                    "server_verify_token": encrypted_token,
                }
            }
        }
        verify_response = session.post(
            verify_url,
            json=verify_payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )

        if "X-GPGAuth-Error" in verify_response.headers:
            error_msg = verify_response.headers["X-GPGAuth-Error"]
            debug_msg = verify_response.headers.get("X-GPGAuth-Debug", "")
            raise ValueError(f"Server verification failed: {error_msg}. Debug: {debug_msg}")

        response_token = verify_response.headers.get("X-GPGAuth-Verify-Response", "")
        if response_token != token:
            raise ValueError("Server verification response token mismatch")

    def _login(self, auth_state: AuthState) -> None:
        """Authenticate using the configured auth method."""
        method = self.config.auth_method
        if method == "jwt":
            self._jwt_login(auth_state)
            auth_state.auth_method = "jwt"
            return

        try:
            self._gpg_login(auth_state.session)
            auth_state.auth_method = "gpg"
        except Exception as gpg_error:
            if method == "gpg":
                raise
            try:
                self._jwt_login(auth_state)
                auth_state.auth_method = "jwt"
            except Exception as jwt_error:
                raise Exception(
                    f"GPG authentication failed: {gpg_error}\n"
                    f"JWT authentication failed: {jwt_error}"
                ) from jwt_error

    def _gpg_login(self, session: requests.Session) -> None:
        """Authenticate with Passbolt using the GPGAuth protocol."""
        server_url = self.config.server_url
        assert server_url is not None
        login_url = urljoin(server_url, "/auth/login.json")
        fingerprint = self.gpg.fingerprint

        payload = {"data": {"gpg_auth": {"keyid": fingerprint}}}
        response = session.post(
            login_url,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )

        if "X-GPGAuth-Error" in response.headers:
            error_msg = response.headers["X-GPGAuth-Error"]
            debug_msg = response.headers.get("X-GPGAuth-Debug", "")
            raise ValueError(f"GPGAuth error: {error_msg}. Debug: {debug_msg}")

        if "X-GPGAuth-User-Auth-Token" not in response.headers:
            raise ValueError("No encrypted token received in X-GPGAuth-User-Auth-Token header")

        encrypted_token = decode_gpgauth_header_value(
            response.headers["X-GPGAuth-User-Auth-Token"]
        )
        decrypted_token = self.gpg.decrypt(encrypted_token).strip()
        check_auth_token_format(decrypted_token)

        verify_payload = {
            "data": {
                "gpg_auth": {
                    "keyid": fingerprint,
                    "user_token_result": decrypted_token,
                }
            }
        }
        final_response = session.post(
            login_url,
            json=verify_payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )

        if "X-GPGAuth-Error" in final_response.headers:
            error_msg = final_response.headers["X-GPGAuth-Error"]
            debug_msg = final_response.headers.get("X-GPGAuth-Debug", "")
            raise ValueError(f"GPGAuth error in final step: {error_msg}. Debug: {debug_msg}")

        authenticated = final_response.headers.get("X-GPGAuth-Authenticated", "false")
        if authenticated.lower() != "true":
            raise ValueError("Authentication not confirmed (X-GPGAuth-Authenticated != true)")

        if not session.cookies:
            raise ValueError("No session cookies received after authentication")

    def _jwt_login(self, auth_state: AuthState) -> None:
        """Authenticate with Passbolt using JWT challenge/response."""
        server_url = self.config.server_url
        assert server_url is not None
        user_id = self.config.user_id
        if not user_id:
            raise ValueError("user_id is required for JWT authentication")

        verify_response = auth_state.session.get(
            urljoin(server_url, "/auth/verify.json"),
            headers={"Accept": "application/json"},
            timeout=30,
        )
        verify_response.raise_for_status()
        verify_payload = verify_response.json()
        server_body = verify_payload.get("body", verify_payload)
        server_key = server_body["keydata"]
        server_fingerprint = self.gpg.fingerprint_from_armored(server_key)

        csrf_token = auth_state.session.cookies.get("csrfToken")
        if not csrf_token:
            raise ValueError("CSRF token not found before JWT login")

        verify_token = str(uuid.uuid4())
        expiry = datetime.now(timezone.utc) + timedelta(seconds=300)
        challenge = {
            "version": "1.0.0",
            "domain": server_url,
            "verify_token": verify_token,
            "verify_token_expiry": int(expiry.timestamp()),
        }
        encrypted_challenge = self.gpg.sign_and_encrypt(
            json.dumps(challenge),
            server_fingerprint,
        )

        login_response = auth_state.session.post(
            urljoin(server_url, "/auth/jwt/login.json"),
            json={"user_id": user_id, "challenge": encrypted_challenge},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-CSRF-Token": csrf_token,
            },
            timeout=30,
        )
        login_response.raise_for_status()
        login_payload = login_response.json()
        login_body = ensure_success(login_payload)
        encrypted_response = login_body["challenge"]
        decrypted_response = json.loads(self.gpg.decrypt(encrypted_response))

        auth_state.jwt_access_token = decrypted_response["access_token"]
        auth_state.jwt_refresh_token = decrypted_response.get("refresh_token")
        auth_state.user_id = user_id
        auth_state.auth_method = "jwt"

    def _refresh_jwt(self, auth_state: AuthState) -> None:
        """Refresh a JWT access token."""
        if not auth_state.jwt_refresh_token:
            raise APIError("JWT refresh token is missing")
        user_id = auth_state.user_id or self.config.user_id
        if not user_id:
            raise APIError("user_id is required to refresh JWT tokens")

        server_url = self.config.server_url
        assert server_url is not None
        http = PassboltHTTPClient(server_url, auth_state)
        body = http.request(
            "POST",
            "/auth/jwt/refresh.json",
            json={"user_id": user_id, "refresh_token": auth_state.jwt_refresh_token},
            allow_reauth=False,
        )
        if isinstance(body, dict):
            auth_state.jwt_access_token = body.get("access_token", auth_state.jwt_access_token)
            auth_state.jwt_refresh_token = body.get(
                "refresh_token", auth_state.jwt_refresh_token
            )

    def _finalize_session(self, auth_state: AuthState) -> None:
        """Populate CSRF token and user id after login."""
        for cookie in auth_state.session.cookies:
            if cookie.name == "csrfToken":
                auth_state.csrf_token = cookie.value

        if not auth_state.user_id:
            auth_state.user_id = self._fetch_user_id(auth_state)

        if auth_state.auth_method == "jwt":
            auth_state.reauthenticate = lambda: self._refresh_jwt(auth_state)

    def _fetch_user_id(self, auth_state: AuthState) -> str:
        """Fetch the current user's UUID from /users/me.json."""
        server_url = self.config.server_url
        assert server_url is not None
        http = PassboltHTTPClient(server_url, auth_state)
        body = http.request("GET", "/users/me.json", allow_reauth=False)
        if isinstance(body, dict) and body.get("id"):
            return str(body["id"])
        raise ValueError("Unable to determine user id from /users/me.json")

    def _resolve_totp_code(self, challenge: dict[str, Any] | None) -> str:
        """Resolve an MFA TOTP code from config or interactive prompt."""
        if self.config.mfa_totp_secret:
            return generate_totp(self.config.mfa_totp_secret)

        providers = (challenge or {}).get("providers", {})
        if not providers.get("totp"):
            raise ValueError("Server did not advertise a TOTP MFA provider")

        if not sys.stdin.isatty():
            raise ValueError(
                "MFA is required but no mfa_totp_secret is configured and stdin is not a TTY"
            )

        while True:
            try:
                code = input("MFA TOTP code: ").strip()
            except (EOFError, KeyboardInterrupt) as exc:
                raise ValueError("MFA input cancelled") from exc
            if code:
                return code
            print("MFA code cannot be empty.", file=sys.stderr)

    def _handle_mfa(
        self,
        auth_state: AuthState,
        challenge: dict[str, Any] | None,
    ) -> None:
        """Complete an MFA challenge and store the resulting cookie."""
        server_url = self.config.server_url
        assert server_url is not None
        last_error: Exception | None = None

        for attempt in range(3):
            totp_code = self._resolve_totp_code(challenge)
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if auth_state.csrf_token:
                headers["X-CSRF-Token"] = auth_state.csrf_token
            if auth_state.jwt_access_token:
                headers["Authorization"] = f"Bearer {auth_state.jwt_access_token}"

            response = auth_state.session.post(
                urljoin(server_url, "/mfa/verify/totp.json"),
                json={"totp": totp_code},
                headers=headers,
                timeout=30,
            )

            if response.status_code == 400 and not self.config.mfa_totp_secret:
                last_error = ValueError("Invalid MFA TOTP code")
                time.sleep(1)
                continue

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                last_error = exc
                if not self.config.mfa_totp_secret:
                    time.sleep(1)
                    continue
                raise

            mfa_cookie = None
            for cookie in response.cookies:
                if cookie.name == "passbolt_mfa":
                    mfa_cookie = cookie.value
            if mfa_cookie is None:
                mfa_cookie = auth_state.session.cookies.get("passbolt_mfa")
            if mfa_cookie is None:
                raise ValueError(
                    "MFA verification succeeded but passbolt_mfa cookie was not set"
                )
            return

        raise ValueError(f"MFA verification failed after 3 attempts: {last_error}")