"""Cookie manager for m.weibo.cn mobile web API authentication.

Handles cookie parsing, storage, validation, and header generation
for the cookie-based Weibo posting workflow.
"""

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

import requests

from src.config import mask_sensitive

logger = logging.getLogger(__name__)

REQUIRED_COOKIE_FIELDS = ("SUB", "SUBP", "XSRF-TOKEN")
WEIBO_CONFIG_URL = "https://m.weibo.cn/api/config"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)


class CookieManager:
    """Manages Weibo cookies: parse, save, load, validate, and generate headers."""

    def __init__(self, cookie_file_path: str):
        self._cookie_file_path = cookie_file_path
        self._data: dict | None = None
        # Attempt to load existing cookies on init
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_cookies(self) -> dict | None:
        """Return the stored cookies dict, or None if not set."""
        self._load()
        if self._data and self._data.get("cookies"):
            return self._data["cookies"]
        return None

    def save_cookies(self, cookies: dict, uid: str = "") -> None:
        """Persist cookies to disk.

        Args:
            cookies: Cookie key-value pairs (must include SUB, SUBP, XSRF-TOKEN).
            uid: Weibo user ID (optional, obtained from /api/config).
        """
        self._data = {
            "cookies": cookies,
            "uid": uid,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "validated_at": "",
            "status": "unknown",
        }
        self._write()
        logger.info(
            "Cookies saved (uid=%s, keys=%s)",
            uid or "unknown",
            ", ".join(f"{k}={mask_sensitive(v)}" for k, v in cookies.items()),
        )

    def parse_cookie_string(self, raw: str) -> dict:
        """Parse a browser Cookie header string into a dict.

        Extracts all key=value pairs. The caller should verify that
        required fields are present.

        Args:
            raw: Raw cookie string, e.g. "SUB=abc; SUBP=def; XSRF-TOKEN=ghi"

        Returns:
            Dict of cookie name -> value.
        """
        cookies: dict[str, str] = {}
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                key, _, value = part.partition("=")
                cookies[key.strip()] = value.strip()
        return cookies

    def validate_cookies(self) -> tuple[bool, str | None]:
        """Check cookie validity by calling /api/config.

        Returns:
            A tuple (is_valid, st_token).
            If login is True, returns (True, st_token).
            If login is False or request fails, returns (False, None).
        """
        cookies = self.load_cookies()
        if not cookies:
            return False, None

        try:
            resp = requests.get(
                WEIBO_CONFIG_URL,
                headers={
                    "Cookie": self.get_cookie_header(),
                    "User-Agent": USER_AGENT,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            logger.warning("Cookie validation request failed: %s", exc)
            self._update_status("unknown")
            return False, None

        config_data = data.get("data", {})
        login = config_data.get("login", False)
        st = config_data.get("st", "")
        uid = str(config_data.get("uid", ""))

        if login and st:
            self._update_status("valid", uid=uid)
            return True, st

        self._update_status("expired")
        return False, None

    def get_cookie_header(self) -> str:
        """Build a Cookie header string from stored cookies.

        Returns:
            A string like "SUB=abc; SUBP=def; XSRF-TOKEN=ghi".
            Returns empty string if no cookies are loaded.
        """
        cookies = self._data.get("cookies", {}) if self._data else {}
        if not cookies:
            return ""
        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    def get_status(self) -> dict:
        """Return current cookie status info.

        Returns:
            Dict with keys: status, uid, updated_at, validated_at, has_cookies.
        """
        self._load()
        if not self._data:
            return {
                "has_cookies": False,
                "status": "unknown",
                "uid": "",
                "updated_at": "",
                "validated_at": "",
            }
        return {
            "has_cookies": bool(self._data.get("cookies")),
            "status": self._data.get("status", "unknown"),
            "uid": self._data.get("uid", ""),
            "updated_at": self._data.get("updated_at", ""),
            "validated_at": self._data.get("validated_at", ""),
        }

    def get_xsrf_token(self) -> str:
        """Return the XSRF-TOKEN cookie value, or empty string."""
        cookies = self._data.get("cookies", {}) if self._data else {}
        return cookies.get("XSRF-TOKEN", "")

    def get_cookie_age_hours(self) -> float | None:
        """Return how many hours have passed since cookies were last updated.

        Returns:
            Hours elapsed as a float, or None if updated_at is not available.
        """
        self._load()
        if not self._data:
            return None
        updated_at_str = self._data.get("updated_at")
        if not updated_at_str:
            return None
        try:
            updated_at = datetime.fromisoformat(updated_at_str)
            now = datetime.now(timezone.utc)
            return (now - updated_at).total_seconds() / 3600
        except (ValueError, TypeError):
            return None

    def is_expiring_soon(self, threshold_hours: float | None = None) -> bool:
        """Check whether cookies are likely to expire soon.

        Args:
            threshold_hours: Hours after which cookies are considered
                expiring soon. Defaults to config.COOKIE_EXPIRY_WARNING_HOURS.

        Returns:
            True if cookie age exceeds the threshold.
        """
        if threshold_hours is None:
            from src.config import COOKIE_EXPIRY_WARNING_HOURS
            threshold_hours = COOKIE_EXPIRY_WARNING_HOURS
        age = self.get_cookie_age_hours()
        if age is None:
            return False
        return age > threshold_hours

    # ------------------------------------------------------------------
    # CookieCloud integration (005 - cookie auto-refresh)
    # ------------------------------------------------------------------

    @staticmethod
    def is_cookiecloud_configured() -> bool:
        """Return True if all CookieCloud config variables are set."""
        from src.config import COOKIECLOUD_SERVER, COOKIECLOUD_UUID, COOKIECLOUD_PASSWORD
        return bool(COOKIECLOUD_SERVER and COOKIECLOUD_UUID and COOKIECLOUD_PASSWORD)

    @staticmethod
    def _decrypt_cookiecloud_legacy(encrypted_b64: str, passphrase: str) -> dict:
        """Decrypt CookieCloud legacy format (CryptoJS OpenSSL / AES-256-CBC).

        Data format: "Salted__" + 8-byte salt + ciphertext, all base64-encoded.
        Key derivation: EVP_BytesToKey (MD5-based) from passphrase + salt.
        """
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad

        raw = base64.b64decode(encrypted_b64)
        # Verify "Salted__" prefix
        if raw[:8] != b"Salted__":
            raise ValueError("Missing 'Salted__' prefix in legacy CookieCloud data")

        salt = raw[8:16]
        ciphertext = raw[16:]

        # EVP_BytesToKey: derive 32-byte key + 16-byte IV using MD5
        key_iv = b""
        prev = b""
        while len(key_iv) < 48:  # 32 (key) + 16 (IV)
            prev = hashlib.md5(prev + passphrase.encode("utf-8") + salt).digest()
            key_iv += prev

        key = key_iv[:32]
        iv = key_iv[32:48]

        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return json.loads(plaintext)

    @staticmethod
    def _decrypt_cookiecloud_fixed(encrypted_b64: str, passphrase: str) -> dict:
        """Decrypt CookieCloud fixed format (AES-128-CBC, zero IV).

        Key: passphrase bytes directly as 16-byte AES key.
        IV: 16 bytes of 0x00.
        """
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad

        ciphertext = base64.b64decode(encrypted_b64)
        key = passphrase.encode("utf-8")[:16]
        iv = b"\x00" * 16

        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return json.loads(plaintext)

    @staticmethod
    def _decrypt_cookiecloud(encrypted_b64: str, uuid: str, password: str,
                             crypto_type: str = "legacy") -> dict:
        """Decrypt CookieCloud data, dispatching by crypto_type."""
        # Derive passphrase: MD5(uuid-password)[:16]
        passphrase = hashlib.md5(f"{uuid}-{password}".encode("utf-8")).hexdigest()[:16]

        if crypto_type == "aes-128-cbc-fixed":
            return CookieManager._decrypt_cookiecloud_fixed(encrypted_b64, passphrase)
        # Default to legacy
        return CookieManager._decrypt_cookiecloud_legacy(encrypted_b64, passphrase)

    def refresh_cookies_via_cookiecloud(self) -> bool:
        """Fetch and apply fresh cookies from CookieCloud server.

        Returns:
            True if cookies were successfully refreshed and validated.
        """
        from src.config import COOKIECLOUD_SERVER, COOKIECLOUD_UUID, COOKIECLOUD_PASSWORD

        url = f"{COOKIECLOUD_SERVER.rstrip('/')}/get/{COOKIECLOUD_UUID}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.ConnectionError:
            logger.warning("CookieCloud server unreachable: %s", COOKIECLOUD_SERVER)
            return False
        except requests.RequestException as exc:
            logger.warning("CookieCloud request failed: %s", exc)
            return False
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("CookieCloud response parse error: %s", exc)
            return False

        encrypted = data.get("encrypted")
        if not encrypted:
            logger.warning("CookieCloud response has no 'encrypted' field")
            return False

        crypto_type = data.get("crypto_type", "legacy")

        try:
            decrypted = self._decrypt_cookiecloud(
                encrypted, COOKIECLOUD_UUID, COOKIECLOUD_PASSWORD, crypto_type
            )
        except Exception as exc:
            logger.warning("CookieCloud decryption failed: %s", exc)
            return False

        # Extract Weibo cookies from cookie_data
        cookie_data = decrypted.get("cookie_data", {})
        weibo_cookies: dict[str, str] = {}

        for domain, cookie_list in cookie_data.items():
            if "weibo" not in domain:
                continue
            if not isinstance(cookie_list, list):
                continue
            for cookie in cookie_list:
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name and value:
                    weibo_cookies[name] = value

        # Verify required fields present
        for field in REQUIRED_COOKIE_FIELDS:
            if field not in weibo_cookies:
                logger.warning("CookieCloud: missing required cookie field: %s", field)
                return False

        # Save and validate
        self.save_cookies(weibo_cookies)
        is_valid, _ = self.validate_cookies()
        if is_valid:
            logger.info("Cookies refreshed via CookieCloud successfully")
            return True

        logger.warning("CookieCloud cookies saved but validation failed")
        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load cookie data from the JSON file."""
        if not os.path.exists(self._cookie_file_path):
            self._data = None
            return
        try:
            with open(self._cookie_file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load cookie file: %s", exc)
            self._data = None

    def _write(self) -> None:
        """Write cookie data to the JSON file with 600 permissions."""
        os.makedirs(os.path.dirname(self._cookie_file_path), exist_ok=True)
        with open(self._cookie_file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.chmod(self._cookie_file_path, 0o600)

    def _update_status(self, status: str, uid: str = "") -> None:
        """Update the status and validated_at fields, then persist."""
        if not self._data:
            return
        self._data["status"] = status
        self._data["validated_at"] = datetime.now(timezone.utc).isoformat()
        if uid:
            self._data["uid"] = uid
        self._write()

