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
# Optional environment variables
# ---------------------------------------------------------------------------
ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID", "")

# ---------------------------------------------------------------------------
# CookieCloud settings (005 - cookie auto-refresh)
# ---------------------------------------------------------------------------
COOKIECLOUD_SERVER: str = os.getenv("COOKIECLOUD_SERVER", "")
COOKIECLOUD_UUID: str = os.getenv("COOKIECLOUD_UUID", "")
COOKIECLOUD_PASSWORD: str = os.getenv("COOKIECLOUD_PASSWORD", "")

# Cookie expiry warning threshold (hours)
COOKIE_EXPIRY_WARNING_HOURS: int = int(os.getenv("COOKIE_EXPIRY_WARNING_HOURS", "36"))

# ---------------------------------------------------------------------------
# Publish queue settings (003 - marketing automation)
# ---------------------------------------------------------------------------

# Optimal publishing times in China Standard Time (UTC+8) as (hour, minute)
PUBLISH_TIMES: list[tuple[int, int]] = [
    (9, 0),   # 중국 시간 09:00 (출근 시간)
    (20, 0),  # 중국 시간 20:00 (저녁 여유 시간)
]

# Maximum posts per day
MAX_DAILY_POSTS: int = 2

# Scheduler check interval in seconds (how often to check the queue)
SCHEDULER_INTERVAL_SECONDS: int = 30 * 60  # 30 minutes

# ---------------------------------------------------------------------------
# Benchmarking settings
# ---------------------------------------------------------------------------

# Day of week for weekly benchmark (0=Monday, 6=Sunday)
BENCHMARK_DAY: int = 6  # Sunday

# Scraping delay between requests (seconds)
SCRAPING_DELAY_MIN: float = 3.0
SCRAPING_DELAY_MAX: float = 5.0

# ---------------------------------------------------------------------------
# Reporting settings
# ---------------------------------------------------------------------------

# Day of week for weekly report (0=Monday)
REPORT_DAY: int = 0  # Monday
REPORT_HOUR_CST: int = 9  # 09:00 CST

# ---------------------------------------------------------------------------
# Expert content settings
# ---------------------------------------------------------------------------

EXPERT_TOPICS: list[str] = [
    "MARKET_TREND",      # 오사카/간사이 부동산 시장 동향
    "INVESTMENT_TIP",    # 일본 부동산 투자 수익률/팁
    "AREA_GUIDE",        # 오사카 근교 지역 소개
    "TAX_VISA",          # 외국인 세금/비자 정보
    "PURCHASE_PROCESS",  # 일본 부동산 매매 절차 안내
]

# Maximum character length for expert content (Weibo format)
EXPERT_CONTENT_MAX_LENGTH: int = 200

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
