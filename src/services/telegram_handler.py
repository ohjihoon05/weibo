import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.services.image_processor import process_image

logger = logging.getLogger(__name__)

MAX_PHOTOS = 9
MEDIA_GROUP_TIMEOUT = 2.0  # seconds

# Resolve IMAGE_DIR from project root (two levels up from this file)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGE_DIR = os.path.join(_PROJECT_ROOT, "data", "images")

# In-memory per-chat mode storage (session-scoped, resets on bot restart)
_chat_modes: dict[int, str] = {}
# Queue mode toggle per chat (True = enqueue instead of immediate publish)
_queue_modes: dict[int, bool] = {}


def get_chat_mode(chat_id: int) -> str:
    """Return the current mode for the given chat. Defaults to 'preview'."""
    return _chat_modes.get(chat_id, "preview")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message explaining bot usage."""
    welcome = (
        "Weibo 자동 포스팅 봇에 오신 것을 환영합니다!\n\n"
        "사진과 매물 정보를 보내주시면 자동으로 중국어로 번역하여 "
        "Weibo에 포스팅합니다.\n\n"
        "사용 가능한 명령어:\n"
        "/preview - 미리보기 모드 (기본값)\n"
        "/auto - 자동 포스팅 모드\n"
        "/queue - 대기열 모드 토글\n"
        "/qstatus - 대기열 현황 조회\n"
        "/status - 현재 모드 및 쿠키 상태\n"
        "/cookie - Weibo 쿠키 설정\n"
        "/competitor - 경쟁 계정 관리\n"
        "/benchmark - 벤치마킹 리포트\n"
        "/report - 주간 성과 리포트\n"
        "/besttime - 최적 발행 시간 분석\n"
        "/optimize - 해시태그 최적화 제안"
    )
    await update.message.reply_text(welcome)


async def cmd_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch the chat to preview mode."""
    chat_id = update.effective_chat.id
    _chat_modes[chat_id] = "preview"
    await update.message.reply_text("미리보기 모드가 활성화되었습니다.")


async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch the chat to auto-posting mode."""
    chat_id = update.effective_chat.id
    _chat_modes[chat_id] = "auto"
    await update.message.reply_text(
        "자동 포스팅 모드가 활성화되었습니다. 다음 매물부터 즉시 포스팅됩니다."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with the current mode and Weibo cookie status."""
    chat_id = update.effective_chat.id
    mode = get_chat_mode(chat_id)
    mode_label = "미리보기 🔍" if mode == "preview" else "자동 포스팅 🚀"

    # Build mode line
    lines = [f"현재 모드: {mode_label}"]

    # Weibo cookie status
    cookie_manager = context.bot_data.get("cookie_manager")
    if cookie_manager:
        status_info = cookie_manager.get_status()
        if not status_info["has_cookies"]:
            lines.append(
                "\n⚠️ Weibo 쿠키가 설정되지 않았습니다. "
                "/cookie <쿠키문자열> 명령어로 설정해주세요."
            )
        else:
            # Live validation
            is_valid, _ = cookie_manager.validate_cookies()
            status_emoji = "✅ 유효" if is_valid else "❌ 만료"
            uid = status_info["uid"] or "unknown"
            updated = status_info["updated_at"][:19].replace("T", " ") if status_info["updated_at"] else "N/A"
            lines.append(f"\n🔑 Weibo 쿠키 상태: {status_emoji}")
            lines.append(f"👤 UID: {uid}")
            lines.append(f"🕐 갱신: {updated}")

    await update.message.reply_text("\n".join(lines))


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle queue mode on/off for the chat."""
    chat_id = update.effective_chat.id
    current = _queue_modes.get(chat_id, False)
    _queue_modes[chat_id] = not current
    if _queue_modes[chat_id]:
        await update.message.reply_text(
            "📋 대기열 모드가 활성화되었습니다.\n"
            "다음 콘텐츠부터 즉시 발행 대신 대기열에 등록됩니다."
        )
    else:
        await update.message.reply_text(
            "📋 대기열 모드가 비활성화되었습니다.\n"
            "다음 콘텐츠부터 기존 방식(즉시/미리보기)으로 처리됩니다."
        )


async def cmd_qstatus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the current publish queue status."""
    from src.storage.publish_queue import JsonPublishQueue
    from src.models.queue_item import QueueItemStatus
    from datetime import datetime, timedelta, timezone

    publish_queue: JsonPublishQueue | None = context.bot_data.get("publish_queue")
    if not publish_queue:
        await update.message.reply_text("⚠️ 대기열이 초기화되지 않았습니다.")
        return

    pending = publish_queue.get_pending()
    today_count = publish_queue.get_today_completed_count()

    cst = timezone(timedelta(hours=8))

    lines = [f"📋 발행 대기열 현황\n"]
    lines.append(f"대기 중: {len(pending)}건")
    lines.append(f"오늘 발행 완료: {today_count}건\n")

    if pending:
        lines.append("📑 대기 항목:")
        for i, item in enumerate(pending, 1):
            try:
                scheduled_utc = datetime.fromisoformat(item.scheduled_at).replace(tzinfo=timezone.utc)
                scheduled_cst = scheduled_utc.astimezone(cst)
                time_str = scheduled_cst.strftime("%m/%d %H:%M CST")
            except (ValueError, AttributeError):
                time_str = "시간 미정"

            type_label = "매물" if item.type == "listing" else "전문가"
            text_preview = item.text[:30] + "..." if len(item.text) > 30 else item.text
            lines.append(f"  {i}. [{type_label}] {time_str}")
            lines.append(f"     {text_preview}")
    else:
        lines.append("대기 중인 항목이 없습니다.")

    # Show queue mode status
    chat_id = update.effective_chat.id
    queue_on = _queue_modes.get(chat_id, False)
    lines.append(f"\n대기열 모드: {'활성' if queue_on else '비활성'}")

    await update.message.reply_text("\n".join(lines))


async def cmd_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set Weibo cookies from a browser Cookie header string.

    Usage: /cookie SUB=xxx; SUBP=yyy; XSRF-TOKEN=zzz; ...
    """
    cookie_manager = context.bot_data.get("cookie_manager")
    if not cookie_manager:
        await update.message.reply_text("❌ 쿠키 매니저가 초기화되지 않았습니다.")
        return

    raw = update.message.text
    # Strip the /cookie prefix
    if raw.startswith("/cookie"):
        raw = raw[len("/cookie"):].strip()

    if not raw:
        await update.message.reply_text(
            "사용법: /cookie <쿠키문자열>\n\n"
            "브라우저에서 m.weibo.cn에 로그인한 후 "
            "DevTools → Network → 요청의 Cookie 헤더를 복사하여 전송해주세요."
        )
        return

    # Parse cookie string
    cookies = cookie_manager.parse_cookie_string(raw)

    # Validate required fields
    missing = [f for f in ("SUB", "SUBP", "XSRF-TOKEN") if f not in cookies]
    if missing:
        await update.message.reply_text(
            f"❌ 필수 쿠키 필드가 누락되었습니다: {', '.join(missing)}\n\n"
            "SUB, SUBP, XSRF-TOKEN이 포함된 전체 쿠키 문자열을 전송해주세요."
        )
        return

    # Save cookies
    cookie_manager.save_cookies(cookies)

    # Validate against /api/config
    is_valid, _ = cookie_manager.validate_cookies()
    if is_valid:
        status_info = cookie_manager.get_status()
        uid = status_info.get("uid", "unknown")
        await update.message.reply_text(
            f"✅ 쿠키 설정 완료. 유효합니다.\n👤 UID: {uid}"
        )
    else:
        await update.message.reply_text(
            "⚠️ 쿠키가 저장되었으나 유효성 검증에 실패했습니다.\n"
            "브라우저에서 m.weibo.cn에 다시 로그인한 후 "
            "새 쿠키를 전송해주세요."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Router: dispatches to media-group or single-photo handler."""
    if update.message.media_group_id is not None:
        await handle_media_group(update, context)
    else:
        await handle_single_photo(update, context)


async def handle_media_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Collect individual photo updates that belong to the same media group.

    Telegram delivers each photo in a media group as a separate Update sharing
    the same ``media_group_id``.  We accumulate them in ``context.chat_data``
    and schedule a one-shot job that fires after *MEDIA_GROUP_TIMEOUT* seconds
    so we can process the whole batch together.
    """
    media_group_id = update.message.media_group_id
    key = f"media_group_{media_group_id}"

    # Largest available resolution is the last element
    file_id = update.message.photo[-1].file_id
    caption = update.message.caption  # may be None

    if key not in context.chat_data:
        # First photo of this group — initialise storage and schedule the job
        context.chat_data[key] = {
            "photos": [file_id],
            "caption": caption,
            "chat_id": update.effective_chat.id,
            "message_id": update.message.message_id,
        }
        context.job_queue.run_once(
            process_media_group,
            MEDIA_GROUP_TIMEOUT,
            data={
                "media_group_id": media_group_id,
                "chat_id": update.effective_chat.id,
            },
            name=f"mg_{media_group_id}",
        )
    else:
        # Subsequent photo — just append
        context.chat_data[key]["photos"].append(file_id)
        if caption and context.chat_data[key]["caption"] is None:
            context.chat_data[key]["caption"] = caption


async def process_media_group(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback: fires after the media-group timeout to process all
    collected photos at once."""
    media_group_id = context.job.data["media_group_id"]
    chat_id = context.job.data["chat_id"]
    key = f"media_group_{media_group_id}"

    # Job callbacks don't have chat_data; access via application
    chat_data = context.application.chat_data.get(chat_id, {})
    group_data = chat_data.get(key)
    if group_data is None:
        logger.warning("Media group %s data missing from chat_data", media_group_id)
        return

    photos = group_data["photos"]
    caption = group_data.get("caption") or ""

    # T017: enforce the 9-photo ceiling
    if len(photos) > MAX_PHOTOS:
        photos = photos[:MAX_PHOTOS]
        await context.bot.send_message(
            chat_id, "⚠️ 사진이 9장을 초과합니다. 처음 9장만 사용됩니다."
        )

    os.makedirs(IMAGE_DIR, exist_ok=True)

    downloaded_paths: list[str] = []
    processed_bytes_list: list[bytes] = []

    for index, file_id in enumerate(photos):
        path = os.path.join(IMAGE_DIR, f"{media_group_id}_{index}.jpg")
        try:
            file = await context.bot.get_file(file_id)
            await file.download_to_drive(path)
            downloaded_paths.append(path)

            processed = process_image(path)
            processed_bytes_list.append(processed)
        except Exception:
            logger.exception(
                "Failed to download/process photo %d of media group %s",
                index,
                media_group_id,
            )

    # Store for downstream consumers and run pipeline
    chat_data["pending_message"] = {
        "photos": processed_bytes_list,
        "caption": caption,
        "chat_id": chat_id,
        "image_paths": downloaded_paths,
    }

    await _run_pipeline(context, chat_id, caption, processed_bytes_list, downloaded_paths)

    # Clean up transient media-group storage
    chat_data.pop(key, None)


async def handle_single_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a single photo message (not part of a media group)."""
    os.makedirs(IMAGE_DIR, exist_ok=True)

    photo = update.message.photo[-1]
    chat_id = update.effective_chat.id
    caption = update.message.caption or ""

    path = os.path.join(IMAGE_DIR, f"{photo.file_id}.jpg")
    file = await context.bot.get_file(photo.file_id)
    await file.download_to_drive(path)

    processed = process_image(path)

    await _run_pipeline(context, chat_id, caption, [processed], [path])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """T016: Handle text-only messages (no photo attached)."""
    chat_id = update.effective_chat.id
    text = update.message.text

    await _run_pipeline(context, chat_id, text, [], [])


async def send_preview(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    formatted_text: str,
    post_id: str,
) -> int:
    """Send a preview message with approve / reject inline keyboard.

    Returns the ``message_id`` of the sent preview message.
    """
    preview_text = f"📋 매물 미리보기\n\n{formatted_text}"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("포스팅", callback_data=f"approve_{post_id}"),
                InlineKeyboardButton("수정 요청", callback_data=f"reject_{post_id}"),
            ]
        ]
    )
    sent_message = await context.bot.send_message(
        chat_id, preview_text, reply_markup=keyboard
    )
    return sent_message.message_id


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline-keyboard button presses (approve / reject / queue management)."""
    query = update.callback_query
    callback_data = query.data
    await query.answer()

    if callback_data.startswith("approve_"):
        post_id = callback_data[len("approve_"):]
        approve_cb = context.bot_data.get("approve_callback")
        if approve_cb:
            await approve_cb(context, update.effective_chat.id, post_id)
    elif callback_data.startswith("reject_"):
        post_id = callback_data[len("reject_"):]
        await query.edit_message_text("수정할 내용을 입력해주세요.")
        reject_cb = context.bot_data.get("reject_callback")
        if reject_cb:
            await reject_cb(context, update.effective_chat.id, post_id)
    elif callback_data.startswith("q_publish_"):
        await _handle_queue_publish_now(query, context, callback_data[len("q_publish_"):])
    elif callback_data.startswith("q_reschedule_"):
        await _handle_queue_reschedule(query, context, callback_data[len("q_reschedule_"):])
    elif callback_data.startswith("q_delete_"):
        await _handle_queue_delete(query, context, callback_data[len("q_delete_"):])


async def _run_pipeline(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    image_bytes_list: list[bytes],
    image_paths: list[str],
) -> None:
    """Invoke the pipeline callback registered in ``bot_data``, or send a
    placeholder acknowledgement if no callback has been wired up yet.

    In *queue* mode, enqueues the content instead of immediate posting.
    In *preview* mode the preview callback is invoked instead of the
    normal pipeline so the user can approve before posting.
    """
    # Queue mode: add to publish queue instead of immediate publish
    if _queue_modes.get(chat_id, False):
        await _enqueue_content(context, chat_id, text, image_paths)
        return

    mode = get_chat_mode(chat_id)
    if mode == "preview":
        preview_callback = context.bot_data.get("preview_callback")
        if preview_callback:
            await preview_callback(context, chat_id, text, image_bytes_list, image_paths)
            return

    # Auto mode — fall through to existing pipeline_callback
    callback = context.bot_data.get("pipeline_callback")
    if callback:
        await callback(context, chat_id, text, image_bytes_list, image_paths)
    else:
        await context.bot.send_message(chat_id, "⏳ 처리 중...")


async def _enqueue_content(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    image_paths: list[str],
) -> None:
    """Enqueue content to the publish queue."""
    from src.storage.publish_queue import JsonPublishQueue
    from src.models.queue_item import QueueItem, QueueItemType
    from src.services.scheduler import get_next_publish_time
    from datetime import datetime, timedelta, timezone

    publish_queue: JsonPublishQueue | None = context.bot_data.get("publish_queue")
    if not publish_queue:
        await context.bot.send_message(chat_id, "⚠️ 대기열이 초기화되지 않았습니다.")
        return

    scheduled_at = get_next_publish_time(publish_queue)

    item = QueueItem(
        type=QueueItemType.listing.value,
        text=text,
        image_paths=image_paths,
        scheduled_at=scheduled_at,
        telegram_chat_id=chat_id,
    )
    publish_queue.enqueue(item)

    # Format scheduled time for display
    cst = timezone(timedelta(hours=8))
    try:
        scheduled_utc = datetime.fromisoformat(scheduled_at).replace(tzinfo=timezone.utc)
        scheduled_cst = scheduled_utc.astimezone(cst)
        time_str = scheduled_cst.strftime("%m/%d %H:%M CST")
    except (ValueError, AttributeError):
        time_str = "시간 계산 중"

    pending_count = publish_queue.get_pending_count()

    # Send confirmation with management buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("지금 발행", callback_data=f"q_publish_{item.id}"),
            InlineKeyboardButton("일정 변경", callback_data=f"q_reschedule_{item.id}"),
            InlineKeyboardButton("삭제", callback_data=f"q_delete_{item.id}"),
        ]
    ])
    await context.bot.send_message(
        chat_id,
        f"📋 대기열에 등록되었습니다.\n"
        f"예정 시간: {time_str}\n"
        f"대기 중: {pending_count}건",
        reply_markup=keyboard,
    )


async def send_error_notification(context, chat_id: int, error_message: str) -> None:
    """Send formatted error message to user."""
    await context.bot.send_message(chat_id, f"\u274c {error_message}")


async def send_retry_notification(context, chat_id: int, attempt: int, max_attempts: int) -> None:
    """Send retry progress notification."""
    await context.bot.send_message(chat_id, f"\u23f3 \ud3ec\uc2a4\ud305 \uc7ac\uc2dc\ub3c4 \uc911... ({attempt}/{max_attempts})")


async def send_exchange_rate_warning(context, chat_id: int, rate_date: str) -> None:
    """Send exchange rate staleness warning."""
    await context.bot.send_message(chat_id, f"\u26a0\ufe0f \ud658\uc728 \uc815\ubcf4\ub97c \uac00\uc838\uc62c \uc218 \uc5c6\uc5b4 {rate_date} \uae30\uc900 \ud658\uc728\uc744 \uc0ac\uc6a9\ud569\ub2c8\ub2e4.")


async def cmd_competitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage competitor accounts: /competitor add|list|remove|search."""
    from src.models.competitor import CompetitorAccount
    from src.storage.json_store import save_competitors, load_competitors

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "사용법:\n"
            "/competitor add <uid> [메모] - 경쟁 계정 추가\n"
            "/competitor list - 등록된 계정 목록\n"
            "/competitor remove <uid> - 계정 제거\n"
            "/competitor search <키워드> - 유사 계정 검색"
        )
        return

    action = args[0].lower()

    if action == "add" and len(args) >= 2:
        uid = args[1]
        note = " ".join(args[2:]) if len(args) > 2 else ""
        competitors = load_competitors()

        if any(c["uid"] == uid for c in competitors):
            await update.message.reply_text(f"이미 등록된 계정입니다: {uid}")
            return

        account = CompetitorAccount(uid=uid, note=note)
        competitors.append(account.to_dict())
        save_competitors(competitors)
        await update.message.reply_text(f"✅ 경쟁 계정 추가 완료: {uid}")

    elif action == "list":
        competitors = load_competitors()
        if not competitors:
            await update.message.reply_text("등록된 경쟁 계정이 없습니다.")
            return
        lines = ["📋 경쟁 계정 목록:\n"]
        for i, c in enumerate(competitors, 1):
            status = "✅" if c.get("active", True) else "❌"
            lines.append(f"{i}. {status} {c.get('nickname', c['uid'])} ({c['uid']})")
            if c.get("note"):
                lines.append(f"   메모: {c['note']}")
        await update.message.reply_text("\n".join(lines))

    elif action == "remove" and len(args) >= 2:
        uid = args[1]
        competitors = load_competitors()
        new_list = [c for c in competitors if c["uid"] != uid]
        if len(new_list) < len(competitors):
            save_competitors(new_list)
            await update.message.reply_text(f"✅ 경쟁 계정 제거 완료: {uid}")
        else:
            await update.message.reply_text(f"해당 계정을 찾을 수 없습니다: {uid}")

    elif action == "search" and len(args) >= 2:
        keyword = " ".join(args[1:])
        await update.message.reply_text(f"🔍 '{keyword}' 검색 중...")

        scraper = context.bot_data.get("weibo_scraper")
        if not scraper:
            await update.message.reply_text("⚠️ 스크래퍼가 초기화되지 않았습니다.")
            return

        try:
            users = scraper.search_users(keyword)
            if not users:
                await update.message.reply_text("검색 결과가 없습니다.")
                return
            lines = [f"🔍 '{keyword}' 검색 결과:\n"]
            for u in users[:10]:
                verified = "✓" if u.get("verified") else ""
                lines.append(f"• {u['nickname']} {verified} (uid: {u['uid']})")
                lines.append(f"  팔로워: {u.get('followers_count', 0)}")
            lines.append("\n/competitor add <uid> 로 등록하세요.")
            await update.message.reply_text("\n".join(lines))
        except Exception as exc:
            await update.message.reply_text(f"검색 실패: {exc}")
    else:
        await update.message.reply_text("잘못된 명령입니다. /competitor 를 입력하면 사용법을 확인할 수 있습니다.")


async def cmd_benchmark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Request the latest benchmark report: /benchmark."""
    analyzer = context.bot_data.get("benchmark_analyzer")
    if not analyzer:
        await update.message.reply_text("⚠️ 벤치마크 분석기가 초기화되지 않았습니다.")
        return

    await update.message.reply_text("📊 벤치마킹 리포트 생성 중...")

    try:
        report = analyzer.generate_benchmark_report()
        if "error" in report:
            await update.message.reply_text(f"⚠️ {report['error']}")
            return
        text = analyzer.format_benchmark_telegram(report)
        await update.message.reply_text(text)
    except Exception as exc:
        logger.exception("Benchmark report error: %s", exc)
        await update.message.reply_text(f"❌ 리포트 생성 실패: {exc}")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the latest weekly performance report: /report."""
    analyzer = context.bot_data.get("benchmark_analyzer")
    if not analyzer:
        await update.message.reply_text("⚠️ 분석기가 초기화되지 않았습니다.")
        return

    try:
        report = analyzer.generate_weekly_report()
        if "error" in report:
            await update.message.reply_text(f"⚠️ {report['error']}")
            return
        text = analyzer.format_weekly_telegram(report)
        await update.message.reply_text(text)
    except Exception as exc:
        logger.exception("Weekly report error: %s", exc)
        await update.message.reply_text(f"❌ 리포트 생성 실패: {exc}")


async def cmd_besttime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show optimal posting time analysis: /besttime."""
    from src.storage.json_store import load_metrics, load_competitor_posts
    from datetime import datetime, timedelta, timezone
    from collections import Counter

    metrics = load_metrics()
    comp_posts = load_competitor_posts()

    if not metrics and not comp_posts:
        await update.message.reply_text(
            "⚠️ 분석에 필요한 데이터가 부족합니다.\n"
            "포스팅과 벤치마킹 데이터가 2주 이상 축적되면 분석이 가능합니다."
        )
        return

    # Analyze competitor posting hours
    hour_engagement = {}
    for post in comp_posts:
        created = post.get("created_at", "")
        try:
            if "T" in created or "-" in created:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                cst_hour = (dt.hour + 8) % 24
                eng = post.get("reposts_count", 0) + post.get("comments_count", 0) + post.get("attitudes_count", 0)
                if cst_hour not in hour_engagement:
                    hour_engagement[cst_hour] = []
                hour_engagement[cst_hour].append(eng)
        except (ValueError, AttributeError):
            continue

    lines = ["⏰ 최적 발행 시간 분석 (CST)\n"]
    if hour_engagement:
        avg_by_hour = {h: sum(v)/len(v) for h, v in hour_engagement.items() if v}
        sorted_hours = sorted(avg_by_hour.items(), key=lambda x: x[1], reverse=True)

        lines.append("시간대별 평균 인게이지먼트:")
        max_eng = max(v for _, v in sorted_hours) if sorted_hours else 1
        for hour, avg in sorted_hours[:8]:
            bar_len = int(avg / max_eng * 10)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            lines.append(f"  {hour:02d}:00 {bar} {avg:.1f}")

        top3 = [f"{h:02d}:00" for h, _ in sorted_hours[:3]]
        lines.append(f"\n추천 시간: {', '.join(top3)}")
    else:
        lines.append("경쟁 계정 데이터가 부족합니다.")
        lines.append("현재 기본 설정: 09:00, 20:00 CST")

    await update.message.reply_text("\n".join(lines))


async def cmd_optimize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show optimization suggestions: /optimize."""
    analyzer = context.bot_data.get("benchmark_analyzer")
    if not analyzer:
        await update.message.reply_text("⚠️ 분석기가 초기화되지 않았습니다.")
        return

    from src.storage.json_store import load_competitor_posts, load_metrics
    comp_posts = load_competitor_posts()
    metrics = load_metrics()

    if not comp_posts and not metrics:
        await update.message.reply_text(
            "⚠️ 최적화 분석에 필요한 데이터가 부족합니다.\n"
            "1개월 이상의 벤치마킹 및 성과 데이터가 필요합니다."
        )
        return

    lines = ["💡 해시태그 & 콘텐츠 최적화 제안\n"]

    # Hashtag analysis from competitors
    if comp_posts:
        from collections import Counter
        all_tags = []
        for p in comp_posts:
            all_tags.extend(p.get("hashtags", []))
        tag_counts = Counter(all_tags).most_common(10)
        if tag_counts:
            lines.append("인기 경쟁 해시태그:")
            for tag, count in tag_counts:
                lines.append(f"  #{tag} ({count}회)")

    # Recommendations
    recs = analyzer._generate_recommendations(comp_posts[-50:] if comp_posts else [])
    if recs:
        lines.append("\n개선 제안:")
        for rec in recs:
            lines.append(f"  • {rec}")

    await update.message.reply_text("\n".join(lines))


async def _handle_queue_publish_now(query, context, item_id: str) -> None:
    """Immediately publish a queued item."""
    from src.storage.publish_queue import JsonPublishQueue
    from src.services.scheduler import process_queue

    publish_queue: JsonPublishQueue | None = context.bot_data.get("publish_queue")
    if not publish_queue:
        await query.edit_message_text("⚠️ 대기열이 초기화되지 않았습니다.")
        return

    item = publish_queue.get_item(item_id)
    if not item:
        await query.edit_message_text("⚠️ 해당 항목을 찾을 수 없습니다.")
        return

    # Set scheduled time to now so it will be dequeued immediately
    from datetime import datetime, timezone
    publish_queue.update_schedule(item_id, datetime.now(timezone.utc).isoformat())
    await query.edit_message_text("🚀 즉시 발행을 시작합니다...")

    # Trigger queue processing
    await process_queue(context)


async def _handle_queue_reschedule(query, context, item_id: str) -> None:
    """Show reschedule options for a queued item."""
    from datetime import datetime, timedelta, timezone
    from src.config import PUBLISH_TIMES

    cst = timezone(timedelta(hours=8))
    now_cst = datetime.now(cst)

    # Offer next few time slots
    slots = []
    for day_offset in range(0, 3):
        check_date = now_cst.date() + timedelta(days=day_offset)
        for hour, minute in PUBLISH_TIMES:
            slot = datetime(check_date.year, check_date.month, check_date.day,
                           hour, minute, tzinfo=cst)
            if slot > now_cst:
                slots.append(slot)
            if len(slots) >= 4:
                break
        if len(slots) >= 4:
            break

    buttons = []
    for slot in slots:
        slot_utc = slot.astimezone(timezone.utc)
        label = slot.strftime("%m/%d %H:%M")
        buttons.append(InlineKeyboardButton(
            label,
            callback_data=f"q_settime_{item_id}_{slot_utc.isoformat()}"
        ))

    keyboard = InlineKeyboardMarkup([buttons[:2], buttons[2:4]] if len(buttons) > 2 else [buttons])
    await query.edit_message_text("새 발행 시간을 선택하세요:", reply_markup=keyboard)


async def _handle_queue_delete(query, context, item_id: str) -> None:
    """Delete an item from the queue."""
    from src.storage.publish_queue import JsonPublishQueue

    publish_queue: JsonPublishQueue | None = context.bot_data.get("publish_queue")
    if not publish_queue:
        await query.edit_message_text("⚠️ 대기열이 초기화되지 않았습니다.")
        return

    removed = publish_queue.remove(item_id)
    if removed:
        await query.edit_message_text("🗑️ 대기열에서 삭제되었습니다.")
    else:
        await query.edit_message_text("⚠️ 해당 항목을 찾을 수 없습니다.")


def get_handlers() -> list:
    """Return the list of handlers to register with the application dispatcher."""
    return [
        CommandHandler("start", cmd_start),
        CommandHandler("preview", cmd_preview),
        CommandHandler("auto", cmd_auto),
        CommandHandler("status", cmd_status),
        CommandHandler("cookie", cmd_cookie),
        CommandHandler("queue", cmd_queue),
        CommandHandler("qstatus", cmd_qstatus),
        CommandHandler("competitor", cmd_competitor),
        CommandHandler("benchmark", cmd_benchmark),
        CommandHandler("report", cmd_report),
        CommandHandler("besttime", cmd_besttime),
        CommandHandler("optimize", cmd_optimize),
        MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo),
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text
        ),
        CallbackQueryHandler(handle_callback),
    ]
