"""Configuration module for the Weibo auto-posting project.

Loads environment variables via python-dotenv and exposes them as validated
settings. Raises ValueError on startup if any required variable is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from src/config.py)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# ---------------------------------------------------------------------------
# Required environment variables
# ---------------------------------------------------------------------------
_REQUIRED_VARS: list[str] = [
    "TELEGRAM_BOT_TOKEN",
    "CLAUDE_API_KEY",
]


def _load_required(name: str) -> str:
    """Return the value of an environment variable or raise ``ValueError``."""
    value = os.getenv(name)
    if not value:
        raise ValueError(
            f"Missing required environment variable: {name}. "
            f"Please set it in your .env file or system environment."
        )
    return value


# Validate and expose every required setting at import time.
TELEGRAM_BOT_TOKEN: str = _load_required("TELEGRAM_BOT_TOKEN")
CLAUDE_API_KEY: str = _load_required("CLAUDE_API_KEY")


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def mask_sensitive(value: str) -> str:
    """Show the first 4 characters and mask the rest with asterisks.

    Useful for safely logging tokens and secrets.

    Examples:
        >>> mask_sensitive("sk-abc123xyz")
        'sk-a*******'
        >>> mask_sensitive("ab")
        '**'
    """
    if len(value) <= 4:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 4)
