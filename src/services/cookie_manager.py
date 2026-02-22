"""Cookie manager for m.weibo.cn mobile web API authentication.

Handles cookie parsing, storage, validation, and header generation
for the cookie-based Weibo posting workflow.
"""

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

    # ------------------------------------------------------------------
    # OpenClaw integration (T015)
    # ------------------------------------------------------------------

    def refresh_cookies_via_openclaw(self) -> bool:
        """Attempt to refresh cookies using OpenClaw browser automation.

        Sends a request to the local OpenClaw instance to perform a
        Weibo login and extract fresh cookies.

        Returns:
            True if cookies were successfully refreshed, False otherwise.
        """
        openclaw_url = "http://localhost:18789"

        try:
            resp = requests.post(
                f"{openclaw_url}/api/tasks",
                json={
                    "skill": "weibo-cookie-refresh",
                    "params": {
                        "url": "https://m.weibo.cn",
                        "action": "login_and_extract_cookies",
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()

            # Extract cookies from OpenClaw response
            new_cookies = result.get("cookies") or result.get("data", {}).get("cookies")
            if not new_cookies or not isinstance(new_cookies, dict):
                logger.warning("OpenClaw returned no cookies")
                return False

            # Verify required fields
            for field in REQUIRED_COOKIE_FIELDS:
                if field not in new_cookies:
                    logger.warning("OpenClaw cookies missing required field: %s", field)
                    return False

            # Save and validate
            self.save_cookies(new_cookies)
            is_valid, _ = self.validate_cookies()
            if is_valid:
                logger.info("Cookies refreshed via OpenClaw successfully")
                return True

            logger.warning("OpenClaw cookies saved but validation failed")
            return False

        except requests.ConnectionError:
            logger.warning("OpenClaw is not running (connection refused)")
            return False
        except requests.RequestException as exc:
            logger.warning("OpenClaw request failed: %s", exc)
            return False
        except (KeyError, ValueError) as exc:
            logger.warning("Failed to parse OpenClaw response: %s", exc)
            return False
