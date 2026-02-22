"""Scheduler for the publish queue.

Calculates optimal publishing times and processes the queue by
dequeuing items at scheduled times and running them through the
existing posting pipeline.
"""

import logging
from datetime import datetime, timedelta, timezone

from src.config import PUBLISH_TIMES, MAX_DAILY_POSTS
from src.storage.publish_queue import JsonPublishQueue
from src.models.queue_item import QueueItem, QueueItemType

logger = logging.getLogger(__name__)

# China Standard Time offset
CST = timezone(timedelta(hours=8))


def get_next_publish_time(publish_queue: JsonPublishQueue) -> str:
    """Calculate the next available publish time slot.

    Uses the fixed time slots from config (default: 09:00 and 20:00 CST).
    Skips slots that already have a scheduled item.

    Returns:
        ISO-format UTC datetime string for the next available slot.
    """
    now_utc = datetime.now(timezone.utc)
    now_cst = now_utc.astimezone(CST)

    # Get already-scheduled times for today and tomorrow
    pending = publish_queue.get_pending()
    scheduled_slots: set[str] = set()
    for item in pending:
        if item.scheduled_at:
            try:
                dt = datetime.fromisoformat(item.scheduled_at).replace(tzinfo=timezone.utc)
                cst_dt = dt.astimezone(CST)
                scheduled_slots.add(cst_dt.strftime("%Y-%m-%d %H:%M"))
            except ValueError:
                continue

    # Check today's and tomorrow's slots
    for day_offset in range(0, 3):  # today, tomorrow, day after
        check_date = now_cst.date() + timedelta(days=day_offset)
        for hour, minute in PUBLISH_TIMES:
            slot_cst = datetime(
                check_date.year, check_date.month, check_date.day,
                hour, minute, tzinfo=CST,
            )
            # Skip past slots
            if slot_cst <= now_cst:
                continue
            # Skip already-scheduled slots
            slot_key = slot_cst.strftime("%Y-%m-%d %H:%M")
            if slot_key in scheduled_slots:
                continue
            # Convert to UTC for storage
            slot_utc = slot_cst.astimezone(timezone.utc)
            return slot_utc.isoformat()

    # Fallback: schedule 24 hours from now
    fallback = now_utc + timedelta(hours=24)
    return fallback.isoformat()


def calculate_optimal_times() -> list[tuple[int, int]]:
    """Calculate optimal posting times from competitor and own performance data.

    Analyzes competitor posting patterns and own post metrics to find
    the 2 best time slots. Falls back to defaults when data is insufficient.

    Returns:
        List of (hour, minute) tuples in CST, sorted by hour.
    """
    from src.storage.json_store import load_competitor_posts, load_metrics
    from collections import Counter

    comp_posts = load_competitor_posts()
    metrics = load_metrics()

    if not comp_posts and not metrics:
        logger.debug("Insufficient data for optimal time calculation, using defaults")
        return list(PUBLISH_TIMES)

    # Collect engagement by hour from competitor posts
    hour_engagement: dict[int, list[float]] = {}

    for post in comp_posts:
        created = post.get("created_at", "")
        try:
            if "T" in created or "-" in created:
                from datetime import datetime as dt_cls
                parsed = dt_cls.fromisoformat(created.replace("Z", "+00:00"))
                cst_hour = (parsed.hour + 8) % 24
                eng = (
                    post.get("reposts_count", 0)
                    + post.get("comments_count", 0)
                    + post.get("attitudes_count", 0)
                )
                hour_engagement.setdefault(cst_hour, []).append(eng)
        except (ValueError, AttributeError):
            continue

    if not hour_engagement:
        return list(PUBLISH_TIMES)

    # Compute average engagement per hour
    avg_by_hour = {
        h: sum(v) / len(v)
        for h, v in hour_engagement.items()
        if v
    }

    # Pick top 2 hours, at least 4 hours apart
    sorted_hours = sorted(avg_by_hour.items(), key=lambda x: x[1], reverse=True)
    optimal: list[int] = []
    for hour, _ in sorted_hours:
        if all(abs(hour - h) >= 4 and abs(hour - h) <= 20 for h in optimal):
            optimal.append(hour)
        if len(optimal) >= 2:
            break

    if len(optimal) < 2:
        return list(PUBLISH_TIMES)

    optimal.sort()
    return [(h, 0) for h in optimal]


async def process_queue(context) -> None:
    """Process the publish queue: dequeue and publish ready items.

    Called periodically by the job_queue. Handles cookie validation
    before attempting to publish (FR-009).

    Args:
        context: Telegram bot context with bot_data containing services.
    """
    publish_queue: JsonPublishQueue = context.bot_data.get("publish_queue")
    if not publish_queue:
        return

    admin_chat_id = context.bot_data.get("admin_chat_id")

    # Check daily limit
    today_count = publish_queue.get_today_completed_count()
    if today_count >= MAX_DAILY_POSTS:
        logger.debug("Daily post limit reached (%d/%d)", today_count, MAX_DAILY_POSTS)
        return

    # Dequeue next ready item
    item = publish_queue.dequeue()
    if not item:
        # No ready items — check if we should generate expert content
        await _maybe_generate_expert(context, publish_queue, today_count)
        return

    logger.info("Processing queue item %s (type=%s)", item.id, item.type)

    # FR-009: Cookie validation before publishing
    cookie_manager = context.bot_data.get("cookie_manager")
    if cookie_manager:
        is_valid, _ = cookie_manager.validate_cookies()
        if not is_valid:
            logger.warning("Cookies invalid, attempting refresh...")
            refreshed = cookie_manager.refresh_cookies_via_openclaw()
            if not refreshed:
                # Cookie refresh failed — pause queue and notify
                publish_queue.fail(item.id, "쿠키 만료 - 자동 갱신 실패")
                item.reset_to_pending()
                publish_queue.enqueue(item)
                publish_queue.remove(item.id)  # remove failed copy
                if admin_chat_id:
                    await context.bot.send_message(
                        admin_chat_id,
                        "⚠️ 쿠키 갱신 실패로 발행이 일시 중단되었습니다.\n"
                        "브라우저에서 m.weibo.cn에 로그인 후 /cookie 명령어로 쿠키를 갱신해주세요.",
                    )
                logger.error("Cookie refresh failed, queue paused")
                return
            logger.info("Cookies refreshed successfully, proceeding with publish")

    # Route to appropriate pipeline based on item type
    try:
        if item.type == QueueItemType.listing.value:
            await _publish_listing(context, item, publish_queue)
        elif item.type == QueueItemType.expert.value:
            await _publish_expert(context, item, publish_queue)
        else:
            publish_queue.fail(item.id, f"Unknown item type: {item.type}")
    except Exception as exc:
        logger.exception("Queue processing error for item %s: %s", item.id, exc)
        publish_queue.fail(item.id, str(exc))
        if admin_chat_id:
            await context.bot.send_message(
                admin_chat_id,
                f"❌ 대기열 발행 실패: {exc}",
            )


async def _maybe_generate_expert(context, publish_queue: JsonPublishQueue, today_count: int) -> None:
    """Generate expert content if the queue is empty and daily goal not met.

    Only triggers if:
    - Queue has no pending items
    - Today's completed count is below MAX_DAILY_POSTS
    - Constitution III: respects preview/auto mode
    """
    if today_count >= MAX_DAILY_POSTS:
        return

    pending_count = publish_queue.get_pending_count()
    if pending_count > 0:
        return  # Items exist but not yet ready (scheduled for later)

    admin_chat_id = context.bot_data.get("admin_chat_id")
    if not admin_chat_id:
        return

    logger.info("Queue empty, daily target not met (%d/%d). Generating expert content...",
                today_count, MAX_DAILY_POSTS)

    try:
        from src.services.expert_generator import ExpertGenerator
        generator = ExpertGenerator()
        content = generator.generate()
        if not content:
            logger.warning("Expert content generation failed")
            if admin_chat_id:
                await context.bot.send_message(
                    admin_chat_id,
                    "⚠️ 전문가 콘텐츠 생성에 실패했습니다. 내일 다시 시도합니다.",
                )
            return

        # Check preview/auto mode (Constitution III)
        from src.services.telegram_handler import get_chat_mode
        mode = get_chat_mode(int(admin_chat_id))

        if mode == "preview":
            # Send preview to admin for approval
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("발행", callback_data=f"expert_approve_{content.id}"),
                    InlineKeyboardButton("건너뛰기", callback_data=f"expert_skip_{content.id}"),
                ]
            ])
            await context.bot.send_message(
                admin_chat_id,
                f"📝 전문가 콘텐츠 미리보기\n\n{content.text_zh}",
                reply_markup=keyboard,
            )
            # Store for later approval
            context.bot_data[f"expert_pending_{content.id}"] = content
        else:
            # Auto mode: enqueue directly
            scheduled_at = get_next_publish_time(publish_queue)
            item = QueueItem(
                type=QueueItemType.expert.value,
                text=content.text_zh,
                scheduled_at=scheduled_at,
                telegram_chat_id=int(admin_chat_id),
            )
            publish_queue.enqueue(item)
            content.mark_queued(item.id)

            from src.storage.json_store import append_expert_content
            append_expert_content(content.to_dict())

            logger.info("Expert content queued: topic=%s, scheduled=%s",
                       content.topic, scheduled_at)

    except Exception as exc:
        logger.exception("Expert content generation error: %s", exc)
        if admin_chat_id:
            await context.bot.send_message(
                admin_chat_id,
                f"⚠️ 전문가 콘텐츠 생성 중 오류: {exc}",
            )


async def _publish_listing(context, item: QueueItem, publish_queue: JsonPublishQueue) -> None:
    """Publish a listing item through the existing pipeline."""
    pipeline_callback = context.bot_data.get("pipeline_callback")
    if not pipeline_callback:
        publish_queue.fail(item.id, "Pipeline callback not configured")
        return

    # Load image bytes if paths exist
    image_bytes_list = []
    for path in item.image_paths:
        try:
            with open(path, "rb") as f:
                image_bytes_list.append(f.read())
        except OSError as exc:
            logger.warning("Failed to read image %s: %s", path, exc)

    chat_id = item.telegram_chat_id or int(context.bot_data.get("admin_chat_id", 0))
    if not chat_id:
        publish_queue.fail(item.id, "No chat_id available")
        return

    # Use the pipeline callback which handles translation, upload, and posting
    await pipeline_callback(context, chat_id, item.text, image_bytes_list, item.image_paths)

    # Assume success if no exception (pipeline sends its own error messages)
    publish_queue.complete(item.id, "pipeline")
    logger.info("Listing item %s published successfully", item.id)


async def _publish_expert(context, item: QueueItem, publish_queue: JsonPublishQueue) -> None:
    """Publish an expert content item (text only, already in Chinese)."""
    from src.services.weibo_client import WeiboClient, CookieExpiredError, WeiboAPIError

    weibo_client: WeiboClient | None = context.bot_data.get("weibo_client")
    if not weibo_client:
        # Try to get it from the module level
        from src.main import weibo_client as main_weibo_client
        weibo_client = main_weibo_client

    if not weibo_client:
        publish_queue.fail(item.id, "WeiboClient not available")
        return

    admin_chat_id = context.bot_data.get("admin_chat_id")

    try:
        weibo_url = weibo_client.create_text_post(item.text)
        publish_queue.complete(item.id, weibo_url)
        logger.info("Expert item %s published: %s", item.id, weibo_url)
        if admin_chat_id:
            await context.bot.send_message(
                admin_chat_id,
                f"✅ 전문가 콘텐츠 자동 발행 완료!\n🔗 {weibo_url}",
            )
    except CookieExpiredError:
        publish_queue.fail(item.id, "쿠키 만료")
        if admin_chat_id:
            await context.bot.send_message(
                admin_chat_id,
                "⚠️ 전문가 콘텐츠 발행 실패: 쿠키 만료. /cookie로 갱신해주세요.",
            )
    except WeiboAPIError as exc:
        publish_queue.fail(item.id, str(exc))
        logger.error("Expert content posting failed: %s", exc)
    except Exception as exc:
        publish_queue.fail(item.id, str(exc))
        logger.exception("Expert content posting error: %s", exc)
