"""Metrics collector for tracking post performance.

Collects engagement data (reposts, comments, likes) from published
Weibo posts at scheduled intervals (2h, 24h, 7d after posting).
"""

import logging
import time
import re

import requests

from src.config import SCRAPING_DELAY_MIN
from src.storage.json_store import append_metrics, list_recent_posts, load_metrics

logger = logging.getLogger(__name__)

BASE_URL = "https://m.weibo.cn"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
MAX_RETRIES = 3
BACKOFF_BASE = 2


class MetricsCollector:
    """Collects post performance metrics from Weibo."""

    def __init__(self, cookie_manager):
        self._cookie_manager = cookie_manager
        self._failed_bids: set[str] = set()  # Track failed bids for retry

    def collect_post_metrics(self, bid: str) -> dict | None:
        """Collect metrics for a single post by bid.

        Args:
            bid: Weibo post bid (from URL).

        Returns:
            Metrics dict or None if collection failed.
        """
        from datetime import datetime
        import uuid

        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(SCRAPING_DELAY_MIN)

                cookie_header = self._cookie_manager.get_cookie_header()
                if not cookie_header:
                    logger.error("No cookies available for metrics collection")
                    return None

                resp = requests.get(
                    f"{BASE_URL}/statuses/show",
                    params={"id": bid},
                    headers={
                        "Cookie": cookie_header,
                        "User-Agent": USER_AGENT,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("ok") != 1:
                    # Check for cookie expiration
                    if "login" in str(data.get("msg", "")).lower():
                        logger.error("Cookie expired during metrics collection")
                        self._failed_bids.add(bid)
                        return None
                    raise ValueError(f"API error: {data.get('msg', 'unknown')}")

                post_data = data.get("data", {})
                metrics = {
                    "id": str(uuid.uuid4()),
                    "bid": bid,
                    "reposts_count": post_data.get("reposts_count", 0),
                    "comments_count": post_data.get("comments_count", 0),
                    "attitudes_count": post_data.get("attitudes_count", 0),
                    "collected_at": datetime.utcnow().isoformat(),
                }

                # Try to extract post_id from data
                post_id = str(post_data.get("id", ""))
                if post_id:
                    metrics["post_id"] = post_id

                # Persist
                append_metrics(metrics)
                self._failed_bids.discard(bid)
                logger.info("Collected metrics for bid %s: reposts=%d, comments=%d, likes=%d",
                           bid, metrics["reposts_count"], metrics["comments_count"],
                           metrics["attitudes_count"])
                return metrics

            except requests.Timeout:
                logger.warning("Timeout collecting metrics for bid %s (attempt %d/%d)",
                             bid, attempt + 1, MAX_RETRIES)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BACKOFF_BASE ** (attempt + 1))
            except requests.RequestException as exc:
                logger.error("Request error for bid %s (attempt %d/%d): %s",
                           bid, attempt + 1, MAX_RETRIES, exc)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BACKOFF_BASE ** (attempt + 1))
            except Exception as exc:
                logger.error("Metrics collection error for bid %s: %s", bid, exc)
                break

        self._failed_bids.add(bid)
        logger.error("Failed to collect metrics for bid %s after %d retries", bid, MAX_RETRIES)
        return None

    def collect_recent_posts(self) -> list[dict]:
        """Collect metrics for recent posts.

        Iterates through the 20 most recent posts, extracts bid from
        weibo_url, and collects metrics with rate limiting.

        Returns:
            List of collected metrics dicts.
        """
        posts = list_recent_posts(limit=20)
        collected = []

        for post in posts:
            weibo_url = post.get("weibo_url", "")
            if not weibo_url:
                continue

            # Extract bid from URL (e.g., https://m.weibo.cn/detail/ABC123)
            bid = self._extract_bid(weibo_url)
            if not bid:
                continue

            # Check if cookie is still valid before each request
            is_valid, _ = self._cookie_manager.validate_cookies()
            if not is_valid:
                logger.error("Cookie expired, stopping metrics collection")
                break

            metrics = self.collect_post_metrics(bid)
            if metrics:
                # Add post_id reference
                metrics["post_id"] = post.get("id", "")
                collected.append(metrics)

        logger.info("Collected metrics for %d/%d posts", len(collected), len(posts))
        return collected

    def get_failed_bids(self) -> set[str]:
        """Return set of bids that failed collection (for retry next cycle)."""
        return self._failed_bids.copy()

    @staticmethod
    def _extract_bid(weibo_url: str) -> str | None:
        """Extract bid from a Weibo post URL."""
        match = re.search(r"/detail/([A-Za-z0-9]+)", weibo_url)
        if match:
            return match.group(1)
        return None
