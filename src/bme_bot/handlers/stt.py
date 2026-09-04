# src/bme_bot/handlers/stt.py
# هندلر ابزار «تبدیل ویس به متن». ساختار عیناً از handlers/ocr.py کپی شده.
#
# duration ویس از متادیتای پیام (voice.duration) قبل از پردازش خوانده و به
# check_stt_limit/increment_stt_usage پاس داده می‌شود (سقف بر مبنای مجموع
# دقیقه‌ی صدا است، نه تعداد فایل — رجوع به db/stt_usage_repository.py).
# ادمین‌ها کامل از این محدودیت معافند (utils.admin.is_admin).

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..db import feature_usage_repository, stt_usage_repository
from ..services import stt_service
from ..utils import admin as admin_utils
from ..utils import error_reporting, messages, persian_text, text_chunking

logger = logging.getLogger(__name__)

# زیر سقف ۲۵MB فایل Groq (تنگ‌ترین محدودیت میان تایرهای زنجیره)، با حاشیه.
_MAX_AUDIO_BYTES = 20 * 1024 * 1024

_PROCESSING_MESSAGE = "⏳ در حال تبدیل ویس به متن... (ممکن است چند ثانیه طول بکشد)"
_NO_TEXT_FOUND_MESSAGE = "متنی در این ویس پیدا نشد. لطفاً یک ویس واضح‌تر امتحان کنید."
_PROVIDER_ERROR_MESSAGE = "مشکلی در سرویس تبدیل ویس به متن پیش آمد. لطفاً کمی بعد دوباره امتحان کنید."
_GENERIC_ERROR_MESSAGE = "متاسفانه در پردازش ویس مشکلی پیش آمد. لطفاً دوباره امتحان کنید."
_PROMPT_FOR_VOICE_MESSAGE = "لطفاً پیام صوتی‌ای که می‌خواهید به متن تبدیل شود را ارسال کنید 🎙"


async def handle_stt_tool_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_stt_voice"] = True
    await update.message.reply_text(_PROMPT_FOR_VOICE_MESSAGE)


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط وقتی awaiting_stt_voice فعال است عمل می‌کند."""
    if not context.user_data.get("awaiting_stt_voice"):
        return

    context.user_data.pop("awaiting_stt_voice", None)
    user_id = update.effective_user.id

    if not stt_service.is_configured():
        await update.message.reply_text(messages.STT_UNAVAILABLE)
        # قبلاً هیچ گزارشی به ادمین نمی‌رفت این‌جا — همون الگوی
        # ai_assistant._require_ai_key_configured/ocr.py.
        await error_reporting.report_service_issue(
            context, "هیچ STT provider ای پیکربندی نشده است.",
            context_label="stt", failure_feature="stt", user_id=user_id,
        )
        return

    voice = update.message.voice
    duration_seconds = voice.duration or 0
    is_admin_user = admin_utils.is_admin(user_id)

    if not is_admin_user:
        can_process, limit_message = await stt_usage_repository.check_stt_limit(
            user_id, duration_seconds,
        )
        if not can_process:
            await update.message.reply_text(f"⚠️ {limit_message}")
            return

    telegram_file = await context.bot.get_file(voice.file_id)
    audio_bytes = bytes(await telegram_file.download_as_bytearray())

    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        await update.message.reply_text(
            "حجم این ویس بیش‌ازحد بزرگ است. لطفاً یک پیام صوتی کوتاه‌تر ارسال کنید."
        )
        return

    if not is_admin_user:
        await stt_usage_repository.record_attempt(user_id)
    processing_message = await update.message.reply_text(_PROCESSING_MESSAGE)

    try:
        result = await stt_service.transcribe(audio_bytes)
    except stt_service.SttServiceUnavailable as e:
        await processing_message.edit_text(messages.STT_UNAVAILABLE)
        await error_reporting.report_service_issue(
            context, str(e), context_label="stt", failure_feature="stt", user_id=user_id,
        )
        return
    except stt_service.SttProviderError as e:
        logger.warning("STT provider chain failed for user %s", user_id)
        await processing_message.edit_text(_PROVIDER_ERROR_MESSAGE)
        alert = str(e)
        if e.__cause__:
            alert = f"{alert}\nعلت: {e.__cause__}"
        await error_reporting.report_service_issue(
            context, alert, context_label="stt", failure_feature="stt", user_id=user_id,
        )
        return
    except Exception as e:
        logger.exception("STT unexpected error for user %s", user_id)
        await processing_message.edit_text(_GENERIC_ERROR_MESSAGE)
        await error_reporting.report_error(
            context, e, context_label="stt", failure_feature="stt", user_id=user_id,
        )
        return

    if not is_admin_user:
        await stt_usage_repository.increment_stt_usage(user_id, duration_seconds)
    await feature_usage_repository.log_usage(user_id, "stt", detail=result.provider)

    if not result.text:
        await processing_message.edit_text(_NO_TEXT_FOUND_MESSAGE)
        return

    cleaned = persian_text.normalize(result.text)
    if not cleaned:
        await processing_message.edit_text(_NO_TEXT_FOUND_MESSAGE)
        return

    chunks = text_chunking.split_into_chunks(cleaned)
    await processing_message.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await update.message.reply_text(chunk)

