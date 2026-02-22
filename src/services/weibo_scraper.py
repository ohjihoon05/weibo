"""Weibo scraper for competitor account monitoring.

Scrapes m.weibo.cn mobile web API to collect competitor posts,
search for similar accounts, and get post details.
Rate-limited to 3-5 seconds between requests.
"""

import logging
import random
import re
import time

import requests

from src.models.competitor import CompetitorPost
from src.config import SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX

logger = logging.getLogger(__name__)

BASE_URL = "https://m.weibo.cn"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
MAX_RETRIES = 3
BACKOFF_BASE = 2


class ScrapingError(Exception):
    """Raised when scraping fails after retries."""
    pass


class AccountInactiveError(ScrapingError):
    """Raised when account is private, deleted, or suspended."""
    pass


class WeiboScraper:
    """Scrapes Weibo mobile web for competitor data."""

    def __init__(self, cookie_header: str = ""):
        self._cookie_header = cookie_header
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        })
        if cookie_header:
            self._session.headers["Cookie"] = cookie_header

    def _delay(self) -> None:
        """Wait random delay between requests."""
        time.sleep(random.uniform(SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX))

    def _request_with_retry(self, url: str, params: dict | None = None) -> dict:
        """Make a GET request with retry and exponential backoff."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                self._delay()
                resp = self._session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                # Check for account issues
                if data.get("ok") == 0:
                    msg = data.get("msg", "")
                    if "不存在" in msg or "已被" in msg or "404" in str(data.get("errno", "")):
                        raise AccountInactiveError(f"Account issue: {msg}")
                    # Other API errors
                    if attempt < MAX_RETRIES - 1:
                        wait = BACKOFF_BASE ** (attempt + 1)
                        logger.warning("API error (attempt %d/%d), retry in %ds: %s",
                                       attempt + 1, MAX_RETRIES, wait, msg)
                        time.sleep(wait)
                        last_error = ScrapingError(msg)
                        continue
                    raise ScrapingError(msg)

                return data

            except AccountInactiveError:
                raise
            except requests.Timeout:
                last_error = ScrapingError(f"Timeout for {url}")
                if attempt < MAX_RETRIES - 1:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    logger.warning("Timeout (attempt %d/%d), retry in %ds", attempt + 1, MAX_RETRIES, wait)
                    time.sleep(wait)
            except requests.RequestException as exc:
                last_error = ScrapingError(str(exc))
                if attempt < MAX_RETRIES - 1:
                    wait = BACKOFF_BASE ** (attempt + 1)
                    logger.warning("Request error (attempt %d/%d), retry in %ds: %s",
                                   attempt + 1, MAX_RETRIES, wait, exc)
                    time.sleep(wait)

        raise last_error or ScrapingError("Max retries exceeded")

    def get_user_posts(self, uid: str, page: int = 1) -> list[CompetitorPost]:
        """Fetch posts from a user's timeline.

        Args:
            uid: Weibo user UID.
            page: Page number (1-indexed).

        Returns:
            List of CompetitorPost objects.
        """
        # containerid for user timeline: 107603{uid}
        container_id = f"107603{uid}"
        url = f"{BASE_URL}/api/container/getIndex"
        params = {
            "type": "uid",
            "value": uid,
            "containerid": container_id,
            "page": page,
        }

        try:
            data = self._request_with_retry(url, params)
        except AccountInactiveError:
            logger.warning("Account %s is inactive/private/deleted", uid)
            raise
        except ScrapingError as exc:
            logger.error("Failed to get posts for uid %s: %s", uid, exc)
            raise

        cards = data.get("data", {}).get("cards", [])
        posts = []
        for card in cards:
            if card.get("card_type") != 9:
                continue
            mblog = card.get("mblog", {})
            if not mblog:
                continue

            # Extract hashtags from text
            text = mblog.get("text", "")
            hashtags = re.findall(r"#([^#]+)#", text)

            # Count images
            pics = mblog.get("pics", [])
            image_count = len(pics) if pics else 0

            post = CompetitorPost(
                id=str(mblog.get("mid", mblog.get("id", ""))),
                competitor_uid=uid,
                text=text,
                image_count=image_count,
                hashtags=hashtags,
                reposts_count=mblog.get("reposts_count", 0),
                comments_count=mblog.get("comments_count", 0),
                attitudes_count=mblog.get("attitudes_count", 0),
                created_at=mblog.get("created_at", ""),
            )
            posts.append(post)

        logger.info("Scraped %d posts from uid %s (page %d)", len(posts), uid, page)
        return posts

    def search_users(self, keyword: str, page: int = 1) -> list[dict]:
        """Search for Weibo users by keyword.

        Args:
            keyword: Search query (e.g., '日本不动产').
            page: Page number.

        Returns:
            List of user info dicts with uid, nickname, followers_count.
        """
        container_id = f"100103type=3&q={keyword}"
        url = f"{BASE_URL}/api/container/getIndex"
        params = {
            "containerid": container_id,
            "page": page,
        }

        try:
            data = self._request_with_retry(url, params)
        except ScrapingError as exc:
            logger.error("User search failed for '%s': %s", keyword, exc)
            return []

        cards = data.get("data", {}).get("cards", [])
        users = []
        for card in cards:
            card_group = card.get("card_group", [])
            for item in card_group:
                user = item.get("user", {})
                if user:
                    users.append({
                        "uid": str(user.get("id", "")),
                        "nickname": user.get("screen_name", ""),
                        "followers_count": user.get("followers_count", 0),
                        "description": user.get("description", ""),
                        "verified": user.get("verified", False),
                    })

        logger.info("Found %d users for keyword '%s'", len(users), keyword)
        return users

    def get_post_detail(self, mid: str) -> dict | None:
        """Get detailed post information by mid.

        Args:
            mid: Weibo post mid/id.

        Returns:
            Post detail dict or None if not found.
        """
        url = f"{BASE_URL}/statuses/show"
        params = {"id": mid}

        try:
            data = self._request_with_retry(url, params)
            return data.get("data", {})
        except ScrapingError as exc:
            logger.error("Failed to get post detail for mid %s: %s", mid, exc)
            return None
