# src/bme_bot/handlers/jozve.py
# هندلر ابزار «ویس استاد به جزوه». هم ویس‌نوت تلگرام هم فایل صوتی آپلودی
# را قبول می‌کند (حداکثر ۲۰ دقیقه). پایپ‌لاین: چک متادیتا (قبل از دانلود)
# → دانلود → stt_service.transcribe() با filename واقعی → ساختاردهی با
# ai_service.ask() (پرامپت مخصوص jozve_prompt.json) → خروجی .md.

from __future__ import annotations

import io
import json
import logging

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from .. import config
from ..db import feature_usage_repository, jozve_usage_repository
from ..services import ai_service, stt_service
from ..utils import admin as admin_utils
from ..utils import error_reporting
from ..utils.rich_message import send_rich_message

logger = logging.getLogger(__name__)

_PROMPT: str | None = None

_MAX_DURATION_SECONDS = 20 * 60
# سقف مستند Telegram Bot API برای دانلود فایل توسط بات (نه سقف provider ها).
_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024

_MIME_TO_EXTENSION = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
}

_PROMPT_FOR_AUDIO_MESSAGE = (
    "لطفاً ویس یا فایل صوتی کلاس رو بفرستید 🎓\n"
    "(حداکثر ۲۰ دقیقه؛ هم ویس تلگرامی هم فایل آپلودی mp3/m4a/wav قبول می‌شه)"
)
_TOO_LONG_MESSAGE = "این فایل بیشتر از ۲۰ دقیقه‌ست. لطفاً یه فایل کوتاه‌تر بفرستید."
_TOO_LARGE_MESSAGE = "حجم این فایل بیش‌ازحد بزرگه (سقف تلگرام ۲۰ مگابایته)."
_STT_UNAVAILABLE_MESSAGE = "سرویس تبدیل ویس به متن فعلاً در دسترس نیست. لطفاً بعداً تلاش کنید."
_AI_UNAVAILABLE_MESSAGE = "سرویس ساختاردهی هوش مصنوعی فعلاً در دسترس نیست. لطفاً بعداً تلاش کنید."
_NO_SPEECH_MESSAGE = "متنی تو این فایل صوتی پیدا نشد. لطفاً یه فایل واضح‌تر امتحان کنید."
_STT_ERROR_MESSAGE = "مشکلی در تبدیل ویس به متن پیش اومد. لطفاً کمی بعد دوباره امتحان کنید."
_STRUCTURING_ERROR_MESSAGE = "متن پیاده شد ولی مشکلی در ساخت جزوه پیش اومد. لطفاً دوباره امتحان کنید."
_GENERIC_ERROR_MESSAGE = "متاسفانه در پردازش فایل مشکلی پیش اومد. لطفاً دوباره امتحان کنید."
_PROCESSING_MESSAGE = "⏳ در حال پردازش فایل صوتی... (ممکنه چند دقیقه طول بکشه)"


def _load_prompt() -> str:
    global _PROMPT
    if _PROMPT is None:
        with open(f"{config.DATA_DIR}/jozve_prompt.json", encoding="utf-8") as f:
            _PROMPT = json.load(f)["system"]
    return _PROMPT


def _determine_filename(message) -> str:
    """ویس‌نوت تلگرام همیشه OGG است. فایل آپلودی معمولاً file_name واقعی
    داره؛ اگه نداشت، از mime_type حدس زده می‌شه (پیش‌فرض mp3، رایج‌ترین
    فرمت فایل موزیک آپلودی در تلگرام)."""
    if message.voice:
        return "voice.ogg"
    audio = message.audio
    if audio.file_name:
        return audio.file_name
    ext = _MIME_TO_EXTENSION.get(audio.mime_type, "mp3")
    return f"audio.{ext}"


async def handle_jozve_tool_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_jozve_audio"] = True
    await update.message.reply_text(_PROMPT_FOR_AUDIO_MESSAGE)


async def handle_jozve_audio_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط وقتی awaiting_jozve_audio فعال است عمل می‌کند. برای voice و
    audio هر دو ثبت می‌شود (group=1، بعد از handler موجود STT در group=0
    که برای همین پیام صوتی خودش کاری نمی‌کند چون پرچم مخصوص خودش ست نشده)."""
    if not context.user_data.get("awaiting_jozve_audio"):
        return
    context.user_data.pop("awaiting_jozve_audio", None)

    message = update.message
    media = message.voice or message.audio
    if media is None:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if media.duration and media.duration > _MAX_DURATION_SECONDS:
        await message.reply_text(_TOO_LONG_MESSAGE)
        return
    if media.file_size and media.file_size > _MAX_DOWNLOAD_BYTES:
        await message.reply_text(_TOO_LARGE_MESSAGE)
        return

    if not stt_service.is_configured():
        await message.reply_text(_STT_UNAVAILABLE_MESSAGE)
        return

    is_admin_user = admin_utils.is_admin(user_id)
    if not is_admin_user:
        can_process, limit_message = await jozve_usage_repository.check_jozve_limit(user_id)
        if not can_process:
            await message.reply_text(f"⚠️ {limit_message}")
            return

    filename = _determine_filename(message)
    telegram_file = await context.bot.get_file(media.file_id)
    audio_bytes = bytes(await telegram_file.download_as_bytearray())

    if len(audio_bytes) > _MAX_DOWNLOAD_BYTES:
        await message.reply_text(_TOO_LARGE_MESSAGE)
        return

    if not is_admin_user:
        await jozve_usage_repository.record_attempt(user_id)
    processing_message = await message.reply_text(_PROCESSING_MESSAGE)

    try:
        stt_result = await stt_service.transcribe(audio_bytes, filename=filename)
    except stt_service.SttServiceUnavailable as e:
        await processing_message.edit_text(_STT_UNAVAILABLE_MESSAGE)
        await error_reporting.report_service_issue(
            context, str(e), context_label="jozve.stt", failure_feature="jozve", user_id=user_id,
        )
        return
    except stt_service.SttProviderError as e:
        logger.warning("Jozve STT chain failed for user %s", user_id)
        await processing_message.edit_text(_STT_ERROR_MESSAGE)
        await error_reporting.report_service_issue(
            context, str(e), context_label="jozve.stt", failure_feature="jozve", user_id=user_id,
        )
        return
    except Exception as e:
        logger.exception("Jozve unexpected STT error for user %s", user_id)
        await processing_message.edit_text(_GENERIC_ERROR_MESSAGE)
        await error_reporting.report_error(
            context, e, context_label="jozve.stt", failure_feature="jozve", user_id=user_id,
        )
        return

    if not stt_result.text:
        # پیاده‌سازی موفق بود، فقط واقعاً حرفی زده نشده - سهمیه مصرف می‌شه
        # (تلاش واقعی انجام شد)، ولی هرگز به مرحله‌ی ساختاردهی نمی‌رسیم.
        if not is_admin_user:
            await jozve_usage_repository.increment_jozve_usage(user_id)
        await feature_usage_repository.log_usage(user_id, "jozve", detail="empty_stt")
        await processing_message.edit_text(_NO_SPEECH_MESSAGE)
        return

    try:
        structured_md, model_used = await ai_service.ask(stt_result.text, _load_prompt())
    except ai_service.AIResponseEmpty as e:
        if not is_admin_user:
            await jozve_usage_repository.increment_jozve_usage(user_id)
        msg = (
            "متاسفانه به دلیل محدودیت‌های ایمنی، امکان ساخت جزوه از این متن نیست."
            if e.blocked else _STRUCTURING_ERROR_MESSAGE
        )
        await processing_message.edit_text(msg)
        return
    except ai_service.AIServiceUnavailable as e:
        await processing_message.edit_text(_AI_UNAVAILABLE_MESSAGE)
        await error_reporting.report_service_issue(
            context, str(e), context_label="jozve.structuring", failure_feature="jozve", user_id=user_id,
        )
        return
    except Exception as e:
        logger.exception("Jozve unexpected structuring error for user %s", user_id)
        await processing_message.edit_text(_GENERIC_ERROR_MESSAGE)
        await error_reporting.report_error(
            context, e, context_label="jozve.structuring", failure_feature="jozve", user_id=user_id,
        )
        return

    if not is_admin_user:
        await jozve_usage_repository.increment_jozve_usage(user_id)
    await feature_usage_repository.log_usage(user_id, "jozve", detail=model_used)

    await processing_message.delete()

    # پیام غنی (Bot API 10.1) برای خوندن فوری جزوه داخل چت، بدون نیاز به
    # دانلود فایل — کاملاً افزوده است: چه موفق بشه چه نه (خطای API، یا
    # محتوای بزرگ‌تر از سقف مجاز send_rich_message)، فایل .md پایین‌تر در
    # هر حال ارسال می‌شود، چون تنها مسیریه که قبلاً هم بدون قید و شرط کار
    # می‌کرده و نباید به این قابلیت اضافه‌ی جدید وابسته بشه.
    await send_rich_message(context.bot, chat_id, structured_md)

    md_bytes = structured_md.encode("utf-8")
    await context.bot.send_document(
        chat_id=chat_id,
        document=InputFile(io.BytesIO(md_bytes), filename="jozve.md"),
        caption="📝 جزوه‌ی شما آماده شد.",
    )
