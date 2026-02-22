"""Weibo client for posting statuses via m.weibo.cn mobile web API.

Uses cookie-based authentication instead of OAuth2. Requires a
CookieManager instance to provide valid session cookies.
"""

import re
import time
import logging
from datetime import datetime, timezone

import requests

from src.config import mask_sensitive

logger = logging.getLogger(__name__)

BASE_URL = "https://m.weibo.cn"
MAX_RETRIES = 3
BACKOFF_SECONDS = [2, 4, 8]
IMAGE_UPLOAD_DELAY = 1  # seconds between image uploads
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)


class WeiboAPIError(Exception):
    """Custom exception for Weibo API errors."""

    def __init__(self, error_code: int | str, error_message: str):
        self.error_code = error_code
        self.error_message = error_message
        super().__init__(f"Weibo API Error {error_code}: {error_message}")


class CookieExpiredError(WeiboAPIError):
    """Raised when Weibo cookies have expired (login=false)."""

    def __init__(self, message: str = "쿠키가 만료되었습니다. /cookie 명령어로 갱신해주세요."):
        super().__init__(error_code="cookie_expired", error_message=message)


class WeiboClient:
    """Client that wraps the m.weibo.cn mobile web API for posting statuses."""

    def __init__(self, cookie_manager):
        """Initialize the client with a CookieManager.

        Args:
            cookie_manager: A CookieManager instance providing cookie access.
        """
        self.cookie_manager = cookie_manager
        self._last_posted_content: str | None = None

    # ------------------------------------------------------------------
    # Internal: st token & headers
    # ------------------------------------------------------------------

    def _get_st_token(self) -> str:
        """Retrieve a fresh st (XSRF) token from /api/config.

        Raises:
            CookieExpiredError: If the cookie session is not logged in.
            WeiboAPIError: If the config request fails.
        """
        is_valid, st = self.cookie_manager.validate_cookies()
        if not is_valid or not st:
            raise CookieExpiredError()
        return st

    def _build_headers(self, st: str) -> dict:
        """Build the required request headers for m.weibo.cn API calls.

        Args:
            st: The XSRF token from /api/config.

        Returns:
            Headers dict with Cookie, X-XSRF-TOKEN, X-Requested-With,
            Referer, and User-Agent.
        """
        return {
            "Cookie": self.cookie_manager.get_cookie_header(),
            "X-XSRF-TOKEN": st,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{BASE_URL}/compose/",
            "User-Agent": USER_AGENT,
        }

    # ------------------------------------------------------------------
    # Retry wrapper
    # ------------------------------------------------------------------

    def _retry_request(self, func, *args, **kwargs):
        """Wrap a function call with retry logic (3 retries, 2/4/8s backoff)."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except CookieExpiredError:
                # Cookie expired is never retryable
                raise
            except WeiboAPIError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait = BACKOFF_SECONDS[attempt]
                    logger.warning("Retry %d/%d after %ds: %s", attempt + 1, MAX_RETRIES, wait, e)
                    time.sleep(wait)
                else:
                    logger.error("All %d retries exhausted: %s", MAX_RETRIES, e)
                    raise
            except requests.RequestException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    wait = BACKOFF_SECONDS[attempt]
                    logger.warning("Network retry %d/%d after %ds: %s", attempt + 1, MAX_RETRIES, wait, e)
                    time.sleep(wait)
                else:
                    raise
        raise last_error

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def upload_image(self, image_bytes: bytes) -> str:
        """Upload an image and return its pic_id.

        Args:
            image_bytes: Raw bytes of the image file (JPEG recommended, <5MB).

        Returns:
            The pic_id string for the uploaded image.

        Raises:
            CookieExpiredError: If the cookie session has expired.
            WeiboAPIError: If the upload API returns an error.
        """
        return self._retry_request(self._upload_image_inner, image_bytes)

    def _upload_image_inner(self, image_bytes: bytes) -> str:
        """Inner upload logic."""
        st = self._get_st_token()
        headers = self._build_headers(st)
        # Remove Content-Type — let requests set multipart boundary
        headers.pop("Content-Type", None)

        response = requests.post(
            f"{BASE_URL}/api/statuses/uploadPic",
            headers=headers,
            data={"st": st},
            files={"pic": ("image.jpg", image_bytes, "image/jpeg")},
            timeout=30,
        )
        data = response.json()

        # Check for error
        if data.get("ok") == 0:
            raise WeiboAPIError(
                error_code=data.get("errno", -1),
                error_message=data.get("msg", "Image upload failed"),
            )

        pic_id = data.get("pic_id")
        if not pic_id:
            raise WeiboAPIError(-1, "No pic_id returned from upload")

        logger.info("Image uploaded: pic_id=%s", pic_id)
        time.sleep(IMAGE_UPLOAD_DELAY)
        return pic_id

    def create_post(self, text: str, pic_ids: list[str]) -> str:
        """Create a status post with optional images.

        Automatically converts hashtag format from #tag to #tag# for Weibo.
        Detects duplicate content and appends timestamp if needed.

        Args:
            text: The status text content.
            pic_ids: List of pic_id strings from upload_image(). Can be empty.

        Returns:
            A URL to the newly created post (https://m.weibo.cn/detail/{bid}).

        Raises:
            CookieExpiredError: If the cookie session has expired.
            WeiboAPIError: If the posting API returns an error.
        """
        result = self._retry_request(self._create_post_inner, text, pic_ids)
        return result

    def _create_post_inner(self, text: str, pic_ids: list[str]) -> str:
        """Inner create-post logic."""
        st = self._get_st_token()
        headers = self._build_headers(st)
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        # Convert hashtags: #tag -> #tag#
        content = self._convert_hashtags(text)

        # Handle duplicate content
        content, self.duplicate_detected = self._handle_duplicate(content)

        payload = {
            "content": content,
            "st": st,
        }
        if pic_ids:
            payload["picId"] = ",".join(pic_ids)

        response = requests.post(
            f"{BASE_URL}/api/statuses/update",
            headers=headers,
            data=payload,
            timeout=30,
        )
        data = response.json()

        if data.get("ok") != 1:
            raise WeiboAPIError(
                error_code=data.get("errno", -1),
                error_message=data.get("msg", "Create post failed"),
            )

        # Extract bid for URL
        post_data = data.get("data", {})
        bid = post_data.get("bid", "")
        if not bid:
            # Fallback to idstr
            bid = post_data.get("idstr", str(post_data.get("id", "")))

        self._last_posted_content = content
        url = f"{BASE_URL}/detail/{bid}"
        logger.info("Post created: %s", url)
        return url

    def create_text_post(self, text: str) -> str:
        """Create a text-only status post (no images).

        Args:
            text: The status text content.

        Returns:
            A URL to the newly created post.

        Raises:
            CookieExpiredError: If the cookie session has expired.
            WeiboAPIError: If the posting API returns an error.
        """
        return self.create_post(text, [])

    # ------------------------------------------------------------------
    # Hashtag conversion (T008)
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_hashtags(text: str) -> str:
        """Convert hashtag format from #tag to #tag# for Weibo.

        Weibo uses the double-hash format: #topic#.
        Leaves already-converted #tag# patterns untouched.

        Args:
            text: Input text with potential #tag format hashtags.

        Returns:
            Text with hashtags converted to #tag# format.
        """
        # Match #tag patterns that are NOT already #tag#
        # Pattern: # followed by non-whitespace, non-# chars, NOT followed by #
        def replace_hashtag(match):
            tag = match.group(1)
            return f"#{tag}#"

        # Find #(non-whitespace, non-#)+ that is NOT followed by #
        return re.sub(r"#([^\s#]+)(?!#)", replace_hashtag, text)

    # ------------------------------------------------------------------
    # Duplicate content detection (T009)
    # ------------------------------------------------------------------

    def _handle_duplicate(self, content: str) -> tuple[str, bool]:
        """Check for duplicate content and append timestamp if needed.

        Args:
            content: The post content to check.

        Returns:
            Tuple of (possibly modified content, duplicate_detected bool).
        """
        if self._last_posted_content and content == self._last_posted_content:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            content = f"{content} ({now})"
            logger.warning("Duplicate content detected, appended timestamp")
            return content, True
        return content, False
