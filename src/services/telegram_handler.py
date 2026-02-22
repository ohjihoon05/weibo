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


def get_chat_mode(chat_id: int) -> str:
    """Return the current mode for the given chat. Defaults to 'preview'."""
    return _chat_modes.get(chat_id, "preview")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message explaining bot usage."""
    welcome = (
        "👋 Weibo 자동 포스팅 봇에 오신 것을 환영합니다!\n\n"
        "사진과 매물 정보를 보내주시면 자동으로 중국어로 번역하여 "
        "Weibo에 포스팅합니다.\n\n"
        "📋 사용 가능한 명령어:\n"
        "/preview - 미리보기 모드 (기본값)\n"
        "/auto - 자동 포스팅 모드\n"
        "/status - 현재 모드 및 쿠키 상태 확인\n"
        "/cookie - Weibo 쿠키 설정\n\n"
        "현재 모드: 미리보기 🔍"
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
    """Handle inline-keyboard button presses (approve / reject)."""
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


async def _run_pipeline(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    image_bytes_list: list[bytes],
    image_paths: list[str],
) -> None:
    """Invoke the pipeline callback registered in ``bot_data``, or send a
    placeholder acknowledgement if no callback has been wired up yet.

    In *preview* mode the preview callback is invoked instead of the
    normal pipeline so the user can approve before posting.
    """
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


async def send_error_notification(context, chat_id: int, error_message: str) -> None:
    """Send formatted error message to user."""
    await context.bot.send_message(chat_id, f"\u274c {error_message}")


async def send_retry_notification(context, chat_id: int, attempt: int, max_attempts: int) -> None:
    """Send retry progress notification."""
    await context.bot.send_message(chat_id, f"\u23f3 \ud3ec\uc2a4\ud305 \uc7ac\uc2dc\ub3c4 \uc911... ({attempt}/{max_attempts})")


async def send_exchange_rate_warning(context, chat_id: int, rate_date: str) -> None:
    """Send exchange rate staleness warning."""
    await context.bot.send_message(chat_id, f"\u26a0\ufe0f \ud658\uc728 \uc815\ubcf4\ub97c \uac00\uc838\uc62c \uc218 \uc5c6\uc5b4 {rate_date} \uae30\uc900 \ud658\uc728\uc744 \uc0ac\uc6a9\ud569\ub2c8\ub2e4.")


def get_handlers() -> list:
    """Return the list of handlers to register with the application dispatcher."""
    return [
        CommandHandler("start", cmd_start),
        CommandHandler("preview", cmd_preview),
        CommandHandler("auto", cmd_auto),
        CommandHandler("status", cmd_status),
        CommandHandler("cookie", cmd_cookie),
        MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo),
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_text
        ),
        CallbackQueryHandler(handle_callback),
    ]
