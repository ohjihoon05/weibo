"""Exchange rate service with fallback chain.

Fetches JPY-to-CNY exchange rate from multiple sources with graceful
degradation: live API -> backup API -> local cache -> hardcoded fallback.
"""

import requests
import logging
from datetime import datetime, timezone
from src.storage.json_store import save_exchange_rate, load_exchange_rate

logger = logging.getLogger(__name__)

HARDCODED_FALLBACK_RATE = 0.048  # Emergency fallback
STALE_WARNING_HOURS = 48
STALE_MAX_HOURS = 168  # 7 days


def get_jpy_to_cny_rate() -> tuple[float, str, str]:
    """Fetch the current JPY-to-CNY exchange rate using a fallback chain.

    Fallback order:
        1. ExchangeRate-API (open.er-api.com)
        2. Frankfurter API (api.frankfurter.dev)
        3. Local cached rate (from data/exchange_rate.json)
        4. Hardcoded fallback constant

    Returns:
        A tuple of (rate, source_description, fetched_date_iso).
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # --- 1. Try ExchangeRate-API ---
    try:
        resp = requests.get(
            "https://open.er-api.com/v6/latest/JPY",
            timeout=10,
        )
        resp.raise_for_status()
        rate = resp.json()["rates"]["CNY"]
        source = "exchangerate-api"
        save_exchange_rate({
            "rate": rate,
            "source": source,
            "fetched_at": now_iso,
        })
        logger.info("Exchange rate fetched from ExchangeRate-API: %s", rate)
        return (rate, source, now_iso)
    except Exception as exc:
        logger.warning("ExchangeRate-API failed: %s", exc)

    # --- 2. Try Frankfurter API ---
    try:
        resp = requests.get(
            "https://api.frankfurter.dev/v1/latest?base=JPY&symbols=CNY",
            timeout=10,
        )
        resp.raise_for_status()
        rate = resp.json()["rates"]["CNY"]
        source = "frankfurter"
        save_exchange_rate({
            "rate": rate,
            "source": source,
            "fetched_at": now_iso,
        })
        logger.info("Exchange rate fetched from Frankfurter: %s", rate)
        return (rate, source, now_iso)
    except Exception as exc:
        logger.warning("Frankfurter API failed: %s", exc)

    # --- 3. Try local cache ---
    cached = load_exchange_rate()
    if cached is not None:
        try:
            fetched_at = datetime.fromisoformat(cached["fetched_at"])
            # Ensure fetched_at is timezone-aware for comparison
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            hours_since = (
                datetime.now(timezone.utc) - fetched_at
            ).total_seconds() / 3600

            if hours_since < STALE_WARNING_HOURS:
                logger.info(
                    "Using cached exchange rate (%.1fh old): %s",
                    hours_since,
                    cached["rate"],
                )
                return (
                    cached["rate"],
                    f"cache ({cached['source']})",
                    cached["fetched_at"],
                )
            elif hours_since < STALE_MAX_HOURS:
                logger.warning(
                    "Using STALE cached exchange rate (%.1fh old, source=%s): %s",
                    hours_since,
                    cached["source"],
                    cached["rate"],
                )
                return (
                    cached["rate"],
                    f"cache-stale ({cached['source']})",
                    cached["fetched_at"],
                )
            else:
                logger.warning(
                    "Cached exchange rate too old (%.1fh), falling through to hardcoded",
                    hours_since,
                )
        except Exception as exc:
            logger.warning("Failed to parse cached exchange rate: %s", exc)

    # --- 4. Hardcoded fallback ---
    logger.warning(
        "All exchange rate sources failed. Using hardcoded fallback: %s",
        HARDCODED_FALLBACK_RATE,
    )
    return (HARDCODED_FALLBACK_RATE, "hardcoded-fallback", now_iso)
