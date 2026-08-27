# src/bme_bot/handlers/ocr.py
# هندلر ابزار «تبدیل عکس به متن».

import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..db import feature_usage_repository, ocr_usage_repository
from ..keyboards import reply_keyboards
from ..services import ocr_service
from ..utils import admin as admin_utils
from ..utils import error_reporting, persian_text, text_chunking
from .menus import make_submenu_handler

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = 15 * 1024 * 1024

_PROCESSING_MESSAGE = "⏳ در حال خواندن متن از عکس... (ممکن است چند ثانیه طول بکشد)"
_NO_TEXT_FOUND_MESSAGE = "متنی در این عکس پیدا نشد. لطفاً یک عکس واضح‌تر امتحان کنید."
_SERVICE_UNAVAILABLE_MESSAGE = "سرویس تبدیل عکس به متن فعلاً در دسترس نیست. لطفاً بعداً تلاش کنید."
_PROVIDER_ERROR_MESSAGE = "مشکلی در سرویس تبدیل عکس به متن پیش آمد. لطفاً کمی بعد دوباره امتحان کنید."
_GENERIC_ERROR_MESSAGE = "متاسفانه در پردازش عکس مشکلی پیش آمد. لطفاً دوباره امتحان کنید."
_PROMPT_FOR_PHOTO_MESSAGE = (
    "لطفاً عکس یا اسکرین‌شاتِ متنِ فارسی‌ای که می‌خواهید تبدیل شود را ارسال کنید 📸"
)

handle_tools_menu = make_submenu_handler(
    reply_keyboards.tools_menu_keyboard,
    "یکی از ابزارهای زیر را انتخاب کنید:",
)


async def handle_ocr_tool_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_ocr_image"] = True
    await update.message.reply_text(_PROMPT_FOR_PHOTO_MESSAGE)


async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط وقتی awaiting_ocr_image فعال است عمل می‌کند."""
    if not context.user_data.get("awaiting_ocr_image"):
        return

    context.user_data.pop("awaiting_ocr_image", None)
    user_id = update.effective_user.id

    if not ocr_service.is_configured():
        await update.message.reply_text(_SERVICE_UNAVAILABLE_MESSAGE)
        return

    is_admin_user = admin_utils.is_admin(user_id)
    if not is_admin_user:
        can_process, limit_message = await ocr_usage_repository.check_ocr_limit(user_id)
        if not can_process:
            await update.message.reply_text(f"⚠️ {limit_message}")
            return

    photo = update.message.photo[-1]
    telegram_file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await telegram_file.download_as_bytearray())

    if len(image_bytes) > _MAX_IMAGE_BYTES:
        await update.message.reply_text(
            "حجم این عکس بیش‌ازحد بزرگ است. لطفاً یک عکس کوچک‌تر ارسال کنید."
        )
        return

    if not is_admin_user:
        await ocr_usage_repository.record_attempt(user_id)
    processing_message = await update.message.reply_text(_PROCESSING_MESSAGE)

    try:
        result = await ocr_service.extract_text(image_bytes)
    except ocr_service.OcrServiceUnavailable as e:
        await processing_message.edit_text(_SERVICE_UNAVAILABLE_MESSAGE)
        await error_reporting.report_service_issue(
            context, str(e), context_label="ocr", failure_feature="ocr", user_id=user_id,
        )
        return
    except ocr_service.OcrProviderError as e:
        logger.warning("OCR provider chain failed for user %s", user_id)
        await processing_message.edit_text(_PROVIDER_ERROR_MESSAGE)
        alert = str(e)
        if e.__cause__:
            alert = f"{alert}\nعلت: {e.__cause__}"
        await error_reporting.report_service_issue(
            context, alert, context_label="ocr", failure_feature="ocr", user_id=user_id,
        )
        return
    except Exception as e:
        logger.exception("OCR unexpected error for user %s", user_id)
        await processing_message.edit_text(_GENERIC_ERROR_MESSAGE)
        await error_reporting.report_error(
            context, e, context_label="ocr", failure_feature="ocr", user_id=user_id,
        )
        return

    if not is_admin_user:
        await ocr_usage_repository.increment_ocr_usage(user_id)
    await feature_usage_repository.log_usage(user_id, "ocr", detail=result.provider)

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