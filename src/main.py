"""Entry point for the Weibo auto-posting bot.

Initializes the Telegram Bot, registers handlers, wires the pipeline,
and starts long-polling.  Supports both auto mode (US1) and preview
mode with approval flow (US2).
"""

import logging
import asyncio
import os
from datetime import time as datetime_time

from telegram.ext import ApplicationBuilder

from src.config import (
    TELEGRAM_BOT_TOKEN, CLAUDE_API_KEY, ADMIN_CHAT_ID,
    mask_sensitive, SCHEDULER_INTERVAL_SECONDS,
)
from src.services.telegram_handler import get_handlers, send_preview
from src.services.translator import TranslatorService
from src.services.weibo_client import WeiboClient, WeiboAPIError, CookieExpiredError
from src.services.cookie_manager import CookieManager
from src.services.exchange_rate import get_jpy_to_cny_rate
from src.services.hashtag_generator import generate_hashtags
from src.services.scheduler import process_queue
from src.services.benchmark_analyzer import BenchmarkAnalyzer
from src.services.metrics_collector import MetricsCollector
from src.models.post import Post, PostHistory, Status, Mode, Action
from src.storage.json_store import save_post, append_history
from src.storage.publish_queue import JsonPublishQueue

logger = logging.getLogger(__name__)

# Module-level service instances (initialised in main())
translator: TranslatorService | None = None
weibo_client: WeiboClient | None = None
cookie_manager: CookieManager | None = None

# Cookie file path (relative to project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE_PATH = os.path.join(_PROJECT_ROOT, "data", "weibo_cookies.json")


async def pipeline_callback(context, chat_id, text, image_bytes_list, image_paths):
    """Core pipeline: translate -> upload images -> post to Weibo.

    Called by the Telegram handler after a message is received.
    """
    post = None
    try:
        # 1. Acknowledge receipt
        await context.bot.send_message(chat_id, "⏳ 처리 중...")

        # 2. Fetch exchange rate
        rate, rate_source, rate_date = get_jpy_to_cny_rate()
        logger.info("Exchange rate: %s (source=%s, date=%s)", rate, rate_source, rate_date)

        # 3. Translate & format
        try:
            listing, formatted_text = translator.translate_and_format(
                text, exchange_rate=rate, exchange_rate_date=rate_date,
            )
        except Exception as exc:
            logger.exception("Translation failed: %s", exc)
            await context.bot.send_message(
                chat_id,
                "❌ 번역 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            )
            return

        # 4. Generate hashtags and append to formatted text
        hashtags = generate_hashtags(listing)
        formatted_text += "\n\n" + " ".join(hashtags)

        # 5. Create Post object (auto mode — skip straight to approved)
        post = Post(
            listing_id=listing.id,
            formatted_text=formatted_text,
            hashtags=hashtags,
            image_paths=image_paths,
            telegram_chat_id=chat_id,
            mode=Mode.auto.value,
            status=Status.approved.value,
        )

        # Log successful translation
        append_history(PostHistory(
            post_id=post.id, attempt_number=1,
            action=Action.translate.value, success=True,
        ).to_dict())

        # 6. Upload images to Weibo (if any)
        pic_ids: list[str] = []
        if image_bytes_list:
            try:
                for image_bytes in image_bytes_list:
                    pic_id = weibo_client.upload_image(image_bytes)
                    pic_ids.append(pic_id)
                    append_history(PostHistory(
                        post_id=post.id, attempt_number=1,
                        action=Action.upload_image.value, success=True,
                    ).to_dict())
            except CookieExpiredError as exc:
                logger.error("Cookie expired during image upload: %s", exc)
                append_history(PostHistory(
                    post_id=post.id, attempt_number=1,
                    action=Action.upload_image.value, success=False,
                    error_message=str(exc), error_code="cookie_expired",
                ).to_dict())
                await context.bot.send_message(
                    chat_id, f"❌ {exc.error_message}"
                )
                return
            except WeiboAPIError as exc:
                logger.exception("Image upload failed: %s", exc)
                append_history(PostHistory(
                    post_id=post.id, attempt_number=1,
                    action=Action.upload_image.value, success=False,
                    error_message=str(exc), error_code=str(exc.error_code),
                ).to_dict())
                await context.bot.send_message(
                    chat_id,
                    "❌ 이미지 업로드 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                )
                return
            except Exception as exc:
                logger.exception("Image upload failed: %s", exc)
                append_history(PostHistory(
                    post_id=post.id, attempt_number=1,
                    action=Action.upload_image.value, success=False,
                    error_message=str(exc),
                ).to_dict())
                await context.bot.send_message(
                    chat_id,
                    "❌ 이미지 업로드 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                )
                return

        # 7. Create Weibo post
        try:
            if pic_ids:
                weibo_url = weibo_client.create_post(formatted_text, pic_ids)
            else:
                weibo_url = weibo_client.create_text_post(formatted_text)

            # T011: Log duplicate detection warning in auto mode
            if getattr(weibo_client, "duplicate_detected", False):
                logger.warning("Duplicate content detected in auto mode for post %s", post.id)

            append_history(PostHistory(
                post_id=post.id, attempt_number=1,
                action=Action.create_post.value, success=True,
            ).to_dict())
        except CookieExpiredError as exc:
            logger.error("Cookie expired during post creation: %s", exc)
            append_history(PostHistory(
                post_id=post.id, attempt_number=1,
                action=Action.create_post.value, success=False,
                error_message=str(exc), error_code="cookie_expired",
            ).to_dict())
            await context.bot.send_message(
                chat_id, f"❌ {exc.error_message}"
            )
            return
        except WeiboAPIError as exc:
            logger.exception("Create post failed: %s", exc)
            append_history(PostHistory(
                post_id=post.id, attempt_number=1,
                action=Action.create_post.value, success=False,
                error_message=str(exc), error_code=str(exc.error_code),
            ).to_dict())
            await context.bot.send_message(
                chat_id,
                "❌ 포스팅 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            )
            return

        post.weibo_url = weibo_url
        post.status = Status.posted.value

        # 8. Persist
        save_post(post.to_dict())

        # 9. Notify success
        await context.bot.send_message(
            chat_id,
            f"✅ Weibo 포스팅 완료!\n🔗 {weibo_url}",
        )

    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)
        if post:
            append_history(PostHistory(
                post_id=post.id, attempt_number=1,
                action=Action.create_post.value, success=False,
                error_message=str(exc),
            ).to_dict())
        await context.bot.send_message(
            chat_id,
            "❌ 포스팅 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )


async def preview_pipeline_callback(context, chat_id, text, image_bytes_list, image_paths):
    """Preview pipeline: translate -> create pending Post -> show preview.

    Instead of posting immediately, presents a preview with approve/reject
    buttons so the user can review before publishing.
    """
    post = None
    try:
        # 1. Acknowledge receipt
        await context.bot.send_message(chat_id, "⏳ 처리 중...")

        # 2. Fetch exchange rate
        rate, rate_source, rate_date = get_jpy_to_cny_rate()
        logger.info("Exchange rate: %s (source=%s, date=%s)", rate, rate_source, rate_date)

        # 3. Translate & format
        try:
            listing, formatted_text = translator.translate_and_format(
                text, exchange_rate=rate, exchange_rate_date=rate_date,
            )
        except Exception as exc:
            logger.exception("Translation failed: %s", exc)
            await context.bot.send_message(
                chat_id,
                "❌ 번역 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            )
            return

        # 4. Generate hashtags and append to formatted text
        hashtags = generate_hashtags(listing)
        formatted_text += "\n\n" + " ".join(hashtags)

        # 5. Create Post object (preview mode — pending approval)
        post = Post(
            listing_id=listing.id,
            formatted_text=formatted_text,
            hashtags=hashtags,
            image_paths=image_paths,
            telegram_chat_id=chat_id,
            mode=Mode.preview.value,
            status=Status.pending_approval.value,
        )

        # Log successful translation
        append_history(PostHistory(
            post_id=post.id, attempt_number=1,
            action=Action.translate.value, success=True,
        ).to_dict())

        # 6. Persist the post
        save_post(post.to_dict())

        # T011: Check for duplicate content in preview mode
        duplicate_warning = ""
        if weibo_client and weibo_client._last_posted_content:
            # Check if the formatted text (after hashtag conversion) would match
            from src.services.weibo_client import WeiboClient
            converted = WeiboClient._convert_hashtags(formatted_text)
            if converted == weibo_client._last_posted_content:
                duplicate_warning = "\n\n⚠️ 직전 게시물과 동일한 내용입니다."

        # 7. Send preview with inline keyboard
        preview_text = formatted_text + duplicate_warning if duplicate_warning else formatted_text
        message_id = await send_preview(context, chat_id, preview_text, post.id)
        post.telegram_message_id = message_id

        # 8. Store pending data so approve_callback can pick it up later
        context.bot_data[f"pending_{post.id}"] = {
            "post": post,
            "image_bytes": image_bytes_list,
            "listing": listing,
        }

    except Exception as exc:
        logger.exception("Preview pipeline error: %s", exc)
        if post:
            append_history(PostHistory(
                post_id=post.id, attempt_number=1,
                action=Action.translate.value, success=False,
                error_message=str(exc),
            ).to_dict())
        await context.bot.send_message(
            chat_id,
            "❌ 미리보기 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )


async def approve_callback(context, chat_id, post_id):
    """Called when the user taps the '포스팅' button on a preview message.

    Retrieves the pending post data, uploads images, creates the Weibo post,
    and notifies the user of success.
    """
    pending_key = f"pending_{post_id}"
    pending = context.bot_data.get(pending_key)
    if pending is None:
        await context.bot.send_message(
            chat_id,
            "⚠️ 해당 매물 데이터를 찾을 수 없습니다. 다시 시도해주세요.",
        )
        return

    post: Post = pending["post"]
    image_bytes_list: list[bytes] = pending["image_bytes"]
    listing = pending["listing"]

    try:
        # 1. Upload images to Weibo (if any)
        pic_ids: list[str] = []
        if image_bytes_list:
            try:
                for image_bytes in image_bytes_list:
                    pic_id = weibo_client.upload_image(image_bytes)
                    pic_ids.append(pic_id)
                    append_history(PostHistory(
                        post_id=post.id, attempt_number=1,
                        action=Action.upload_image.value, success=True,
                    ).to_dict())
            except CookieExpiredError as exc:
                logger.error("Cookie expired during image upload: %s", exc)
                append_history(PostHistory(
                    post_id=post.id, attempt_number=1,
                    action=Action.upload_image.value, success=False,
                    error_message=str(exc), error_code="cookie_expired",
                ).to_dict())
                await context.bot.send_message(
                    chat_id, f"❌ {exc.error_message}"
                )
                return
            except WeiboAPIError as exc:
                logger.exception("Image upload failed: %s", exc)
                append_history(PostHistory(
                    post_id=post.id, attempt_number=1,
                    action=Action.upload_image.value, success=False,
                    error_message=str(exc), error_code=str(exc.error_code),
                ).to_dict())
                await context.bot.send_message(
                    chat_id,
                    "❌ 이미지 업로드 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                )
                return
            except Exception as exc:
                logger.exception("Image upload failed: %s", exc)
                append_history(PostHistory(
                    post_id=post.id, attempt_number=1,
                    action=Action.upload_image.value, success=False,
                    error_message=str(exc),
                ).to_dict())
                await context.bot.send_message(
                    chat_id,
                    "❌ 이미지 업로드 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                )
                return

        # 2. Create Weibo post
        try:
            if pic_ids:
                weibo_url = weibo_client.create_post(post.formatted_text, pic_ids)
            else:
                weibo_url = weibo_client.create_text_post(post.formatted_text)
            append_history(PostHistory(
                post_id=post.id, attempt_number=1,
                action=Action.create_post.value, success=True,
            ).to_dict())
        except CookieExpiredError as exc:
            logger.error("Cookie expired during post creation: %s", exc)
            append_history(PostHistory(
                post_id=post.id, attempt_number=1,
                action=Action.create_post.value, success=False,
                error_message=str(exc), error_code="cookie_expired",
            ).to_dict())
            await context.bot.send_message(
                chat_id, f"❌ {exc.error_message}"
            )
            return
        except WeiboAPIError as exc:
            logger.exception("Create post failed: %s", exc)
            append_history(PostHistory(
                post_id=post.id, attempt_number=1,
                action=Action.create_post.value, success=False,
                error_message=str(exc), error_code=str(exc.error_code),
            ).to_dict())
            await context.bot.send_message(
                chat_id,
                "❌ 포스팅 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            )
            return

        post.weibo_url = weibo_url
        post.status = Status.posted.value

        # 3. Persist updated post
        save_post(post.to_dict())

        # 4. Notify success
        await context.bot.send_message(
            chat_id,
            f"✅ Weibo 포스팅 완료!\n🔗 {weibo_url}",
        )

    except Exception as exc:
        logger.exception("Approve callback error: %s", exc)
        append_history(PostHistory(
            post_id=post.id, attempt_number=1,
            action=Action.create_post.value, success=False,
            error_message=str(exc),
        ).to_dict())
        await context.bot.send_message(
            chat_id,
            "❌ 포스팅 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        )
    finally:
        # Clean up pending data
        context.bot_data.pop(pending_key, None)


# ------------------------------------------------------------------
# Periodic cookie validation job (T016)
# ------------------------------------------------------------------

async def cookie_validation_job(context) -> None:
    """Periodic job: validate cookies and attempt auto-refresh if expired.

    Runs every 6 hours via job_queue. If cookies are invalid, tries
    OpenClaw auto-refresh. On failure, sends notification to the user.
    """
    cm = context.bot_data.get("cookie_manager")
    admin_chat_id = context.bot_data.get("admin_chat_id")
    if not cm or not admin_chat_id:
        return

    is_valid, _ = cm.validate_cookies()
    if is_valid:
        logger.info("Periodic cookie check: valid")
        return

    # Check if cookies need refresh (updated_at > 24h ago)
    status_info = cm.get_status()
    if not status_info["has_cookies"]:
        return

    logger.warning("Periodic cookie check: invalid, attempting OpenClaw refresh")

    # Attempt OpenClaw auto-refresh
    refreshed = cm.refresh_cookies_via_openclaw()
    if refreshed:
        logger.info("Cookies auto-refreshed via OpenClaw")
        await context.bot.send_message(
            admin_chat_id,
            "🔄 Weibo 쿠키가 자동으로 갱신되었습니다.",
        )
    else:
        # T017: Fallback notification
        logger.warning("OpenClaw auto-refresh failed")
        await context.bot.send_message(
            admin_chat_id,
            "⚠️ 자동 쿠키 갱신에 실패했습니다. "
            "브라우저에서 m.weibo.cn에 로그인한 후 "
            "/cookie 명령어로 쿠키를 설정해주세요.",
        )


async def _benchmark_job(context) -> None:
    """Weekly job: collect competitor posts and generate benchmark report."""
    analyzer = context.bot_data.get("benchmark_analyzer")
    admin_chat_id = context.bot_data.get("admin_chat_id")
    if not analyzer or not admin_chat_id:
        return

    try:
        logger.info("Starting weekly benchmark collection...")
        summary = analyzer.collect_competitor_posts()
        report = analyzer.generate_benchmark_report()
        text = analyzer.format_benchmark_telegram(report)
        await context.bot.send_message(admin_chat_id, text)
        logger.info("Weekly benchmark report sent")
    except Exception as exc:
        logger.exception("Benchmark job error: %s", exc)
        if admin_chat_id:
            await context.bot.send_message(
                admin_chat_id, f"❌ 주간 벤치마킹 실패: {exc}"
            )


async def _weekly_report_job(context) -> None:
    """Weekly job: generate and send performance report."""
    analyzer = context.bot_data.get("benchmark_analyzer")
    admin_chat_id = context.bot_data.get("admin_chat_id")
    if not analyzer or not admin_chat_id:
        return

    try:
        logger.info("Generating weekly performance report...")
        report = analyzer.generate_weekly_report()
        if "error" not in report:
            text = analyzer.format_weekly_telegram(report)
            await context.bot.send_message(admin_chat_id, text)
            logger.info("Weekly performance report sent")
        else:
            logger.info("No data for weekly report: %s", report.get("error"))
    except Exception as exc:
        logger.exception("Weekly report job error: %s", exc)


async def _metrics_collection_job(context) -> None:
    """Job: collect metrics for a specific post (one-shot, scheduled after publish)."""
    bid = context.job.data.get("bid")
    post_id = context.job.data.get("post_id")
    collector = context.bot_data.get("metrics_collector")
    if not collector or not bid:
        return

    try:
        metrics = collector.collect_post_metrics(bid)
        if metrics and post_id:
            metrics["post_id"] = post_id
        logger.info("Metrics collected for bid %s", bid)
    except Exception as exc:
        logger.error("Metrics collection failed for bid %s: %s", bid, exc)


async def _monthly_optimization_job(context) -> None:
    """Monthly job: generate and send optimization suggestions."""
    analyzer = context.bot_data.get("benchmark_analyzer")
    admin_chat_id = context.bot_data.get("admin_chat_id")
    if not analyzer or not admin_chat_id:
        return

    try:
        from src.storage.json_store import load_competitor_posts, load_metrics
        from collections import Counter

        comp_posts = load_competitor_posts()
        metrics = load_metrics()

        if not comp_posts and not metrics:
            logger.info("No data for monthly optimization")
            return

        lines = ["💡 월간 해시태그 & 콘텐츠 최적화 분석\n"]

        if comp_posts:
            all_tags = []
            for p in comp_posts:
                all_tags.extend(p.get("hashtags", []))
            tag_counts = Counter(all_tags).most_common(10)
            if tag_counts:
                lines.append("인기 경쟁 해시태그:")
                for tag, count in tag_counts:
                    lines.append(f"  #{tag} ({count}회)")

        recs = analyzer._generate_recommendations(comp_posts[-50:] if comp_posts else [])
        if recs:
            lines.append("\n개선 제안:")
            for rec in recs:
                lines.append(f"  • {rec}")

        await context.bot.send_message(admin_chat_id, "\n".join(lines))
        logger.info("Monthly optimization report sent")
    except Exception as exc:
        logger.exception("Monthly optimization job error: %s", exc)


def schedule_metrics_collection(app, bid: str, post_id: str) -> None:
    """Schedule metrics collection at 2h, 24h, and 7d after posting."""
    intervals = [
        (2 * 3600, "2h"),      # 2 hours
        (24 * 3600, "24h"),    # 24 hours
        (7 * 24 * 3600, "7d"), # 7 days
    ]
    for delay, label in intervals:
        app.job_queue.run_once(
            _metrics_collection_job,
            when=delay,
            data={"bid": bid, "post_id": post_id},
            name=f"metrics_{bid}_{label}",
        )
    logger.info("Metrics collection scheduled for bid %s at 2h/24h/7d", bid)


def main():
    """Bootstrap logging, services, handlers, and start long-polling."""
    # Create logs directory
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, "bot.log"), encoding="utf-8"),
        ],
    )

    logger.info("Initializing Weibo auto-posting bot...")
    logger.info("Telegram token: %s", mask_sensitive(TELEGRAM_BOT_TOKEN))
    logger.info("Claude API key: %s", mask_sensitive(CLAUDE_API_KEY))

    global translator, weibo_client, cookie_manager
    translator = TranslatorService(CLAUDE_API_KEY)
    cookie_manager = CookieManager(COOKIE_FILE_PATH)
    weibo_client = WeiboClient(cookie_manager)

    # Log cookie status
    cookie_status = cookie_manager.get_status()
    if cookie_status["has_cookies"]:
        logger.info("Weibo cookies loaded (uid=%s, status=%s)", cookie_status["uid"], cookie_status["status"])
    else:
        logger.info("No Weibo cookies configured. Use /cookie command to set them.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    for handler in get_handlers():
        app.add_handler(handler)

    # Initialize publish queue
    publish_queue = JsonPublishQueue()
    recovered = publish_queue.recover_stale_processing()
    if recovered:
        logger.info("Recovered %d stale queue items on startup", recovered)

    # Initialize benchmark analyzer and metrics collector
    try:
        from src.services.weibo_scraper import WeiboScraper
        scraper = WeiboScraper(cookie_header=cookie_manager.get_cookie_header())
        benchmark_analyzer = BenchmarkAnalyzer(scraper=scraper)
        metrics_collector = MetricsCollector(cookie_manager=cookie_manager)
    except Exception as exc:
        logger.warning("Failed to init scraper/analyzer: %s", exc)
        scraper = None
        benchmark_analyzer = BenchmarkAnalyzer()
        metrics_collector = None

    # Wire pipeline callbacks so handlers can invoke them
    app.bot_data["pipeline_callback"] = pipeline_callback
    app.bot_data["preview_callback"] = preview_pipeline_callback
    app.bot_data["approve_callback"] = approve_callback
    app.bot_data["cookie_manager"] = cookie_manager
    app.bot_data["publish_queue"] = publish_queue
    app.bot_data["weibo_client"] = weibo_client
    app.bot_data["benchmark_analyzer"] = benchmark_analyzer
    app.bot_data["metrics_collector"] = metrics_collector
    if scraper:
        app.bot_data["weibo_scraper"] = scraper

    # Admin chat ID for notifications
    app.bot_data["admin_chat_id"] = ADMIN_CHAT_ID

    # Schedule periodic cookie validation (every 6 hours)
    if ADMIN_CHAT_ID:
        app.job_queue.run_repeating(
            cookie_validation_job,
            interval=6 * 60 * 60,  # 6 hours
            first=60,  # First check after 1 minute
            name="cookie_validation",
        )
        logger.info("Periodic cookie validation scheduled (every 6 hours)")

    # Schedule queue processing (check every 30 minutes)
    app.job_queue.run_repeating(
        process_queue,
        interval=SCHEDULER_INTERVAL_SECONDS,
        first=30,  # First check after 30 seconds
        name="queue_processor",
    )
    logger.info("Queue processor scheduled (every %d seconds)", SCHEDULER_INTERVAL_SECONDS)

    # Schedule weekly benchmarking (Sunday evening CST = Sunday 11:00 UTC)
    app.job_queue.run_daily(
        _benchmark_job,
        time=datetime_time(hour=11, minute=0),  # 19:00 CST = 11:00 UTC
        days=(6,),  # Sunday
        name="weekly_benchmark",
    )
    logger.info("Weekly benchmark scheduled (Sunday 19:00 CST)")

    # Schedule weekly performance report (Monday morning CST = Monday 01:00 UTC)
    app.job_queue.run_daily(
        _weekly_report_job,
        time=datetime_time(hour=1, minute=0),  # 09:00 CST = 01:00 UTC
        days=(0,),  # Monday
        name="weekly_report",
    )
    logger.info("Weekly report scheduled (Monday 09:00 CST)")

    # Schedule monthly optimization analysis (1st of each month, 10:00 CST = 02:00 UTC)
    app.job_queue.run_monthly(
        _monthly_optimization_job,
        when=datetime_time(hour=2, minute=0),  # 10:00 CST = 02:00 UTC
        day=1,
        name="monthly_optimization",
    )
    logger.info("Monthly optimization scheduled (1st of month, 10:00 CST)")

    # Start Flask API server in a daemon thread (T032)
    try:
        import threading
        from src.api.routes import create_app
        flask_app = create_app(publish_queue)
        flask_thread = threading.Thread(
            target=flask_app.run,
            kwargs={"host": "127.0.0.1", "port": 5000, "use_reloader": False},
            daemon=True,
        )
        flask_thread.start()
        logger.info("Flask API server started on http://127.0.0.1:5000")
    except Exception as exc:
        logger.warning("Failed to start Flask API server: %s", exc)

    logging.info("Bot started. Listening for messages...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
