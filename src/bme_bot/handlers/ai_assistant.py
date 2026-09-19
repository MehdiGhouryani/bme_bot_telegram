# src/bme_bot/handlers/ai_assistant.py
# مسیرهای /ask، /ai و دکمه پرسش از هوش مصنوعی.

from __future__ import annotations

import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from .. import config
from ..db import ai_usage_repository, feature_usage_repository
from ..services import ai_service
from ..utils import error_reporting, messages, rich_message, text_chunking
from ..utils.admin import is_admin
from ..utils.draft_stream import stream_preview

logger = logging.getLogger(__name__)

_PROMPTS: dict | None = None


def _load_prompts() -> dict:
    global _PROMPTS
    if _PROMPTS is None:
        with open(f"{config.DATA_DIR}/ai_prompts.json", encoding="utf-8") as f:
            _PROMPTS = json.load(f)
    return _PROMPTS


def _public_system_prompt() -> str:
    return _load_prompts()["public"]


def _admin_system_prompt() -> str:
    return _load_prompts()["admin"]


async def send_error_to_admins(
    context: ContextTypes.DEFAULT_TYPE,
    error: Exception,
    command_name: str = "N/A",
    user_id: int | None = None,
):
    await error_reporting.report_error(
        context, error,
        context_label=f"/{command_name}",
        failure_feature="ai",
        user_id=user_id,
    )


async def _require_ai_key_configured(
    context: ContextTypes.DEFAULT_TYPE, chat_id, *, context_label: str, user_id: int | None = None,
) -> bool:
    if not config.GEMINI_API_KEY:
        try:
            await context.bot.send_message(chat_id=chat_id, text=messages.AI_UNAVAILABLE)
        except Exception as e:
            logger.debug("soft unavailable notice failed: %s", e)
        # قبلاً این‌جا هیچ report_service_issue‌ای نبود — چون این پیش‌چک
        # همیشه *قبل* از try/except رسیدن به ai_service.ask() صدا زده
        # می‌شه، شاخه‌ی except ai_service.AIServiceUnavailable پایین‌تر
        # (که تنها جای صدا زدن report_service_issue برای این وضعیت بود)
        # عملاً هیچ‌وقت اجرا نمی‌شد — یعنی اگه GEMINI_API_KEY خالی باشه،
        # هیچ هشدار تلگرامی به ادمین نمی‌رفت (فقط یه لاگ ERROR یه‌بار موقع
        # استارت بات، تو ai_service.py). حالا این‌جا مستقیم گزارش می‌شه.
        await error_reporting.report_service_issue(
            context, "GEMINI_API_KEY تنظیم نشده است.",
            context_label=context_label, failure_feature="ai", user_id=user_id,
        )
        return False
    return True


async def _report_unexpected_error(
    context: ContextTypes.DEFAULT_TYPE,
    error: Exception,
    *,
    command_name: str,
    chat_id,
    user_id: int,
):
    await send_error_to_admins(context, error, command_name=command_name, user_id=user_id)
    try:
        await context.bot.send_message(chat_id=chat_id, text=messages.GENERIC_UNAVAILABLE)
    except Exception as e:
        logger.debug("soft unexpected notice failed: %s", e)


async def _safe_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int) -> None:
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def _send_reply_chunks(
    send_fn, full_text: str, *, bot, chat_id, reply_to_message_id: int | None = None,
):
    """هر چانک را اول با sendRichMessage (جدول/تیتر/لیست بومی، بدون نیاز
    به escape دستی MarkdownV2 — رجوع به utils/rich_message.py) امتحان
    می‌کند؛ روی هر مانعی (محتوای بیش از سقف ۳۲۷۶۸ بایتی، یا هر خطای
    واقعی API) rich_message.send_rich_message بی‌صدا False برمی‌گرداند و
    این تابع دقیقاً به همون مسیر قدیمی و همیشه-کارکرده (MarkdownV2 با
    fallback متن ساده روی BadRequest) برمی‌گرده — یعنی این تغییر عمداً
    فقط یه لایه‌ی *اضافه* روی رفتار قبلیه، نه جایگزینش؛ رفتار قبلی حتی
    یک خط هم عوض نشده، فقط قبلش یه تلاش اول اضافه شده.

    reply_to_message_id فقط برای مسیر /ai (پاسخ به یک پیام مشخص) لازمه —
    وقتی مقدار داره، به‌شکل reply_parameters به sendRichMessage پاس داده
    می‌شه تا رفتار reply-threading کنونی (original_message.reply_text)
    حتی روی مسیر جدید هم حفظ بشه."""
    extra = {"reply_parameters": {"message_id": reply_to_message_id}} if reply_to_message_id else {}
    for chunk in text_chunking.split_into_chunks(full_text):
        if await rich_message.send_rich_message(bot, chat_id, chunk, **extra):
            continue
        try:
            await send_fn(chunk, ParseMode.MARKDOWN_V2)
        except BadRequest as e:
            if "Can't parse entities" in str(e):
                logger.warning("markdown parse failed — plain text fallback")
                await send_fn(chunk, None)
            else:
                raise


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update or not update.effective_chat:
        logger.error("ask_command: invalid update")
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_question = " ".join(context.args).strip() if context.args else ""

    if not user_question:
        await context.bot.send_message(
            chat_id=chat_id,
            text="لطفاً سوال خود را پس از دستور /ask بنویسید یا از دکمه هوش مصنوعی استفاده کنید.",
        )
        return

    await ask_user_question(
        context, chat_id, user_question, user_id,
        is_private_chat=update.effective_chat.type == ChatType.PRIVATE,
    )


async def ask_user_question(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_question: str, user_id: int,
    is_private_chat: bool = False,
) -> bool:
    """True = تلاش انجام شد (موفق یا ناموفق با پیام نهایی). False = رد شد قبل از تلاش.
    is_private_chat: برای پیش‌نمایش تدریجی draft لازم است (sendRichMessageDraft
    فقط در چت خصوصی کار می‌کند) — رجوع به utils/draft_stream.py."""
    if not await _require_ai_key_configured(context, chat_id, context_label="/ask", user_id=user_id):
        return False

    if not is_admin(user_id):
        can_ask, limit_message = await ai_usage_repository.check_ai_limit(user_id)
        if not can_ask:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {limit_message}")
            return False
        await ai_usage_repository.record_attempt(user_id)

    try:
        processing_message = await context.bot.send_message(
            chat_id=chat_id, text="⏳ در حال پردازش سوال شما...",
        )
        system_prompt = _public_system_prompt()

        try:
            full_text, model_used = await ai_service.ask(user_question, system_prompt)
        except ai_service.AIResponseEmpty as e:
            await _safe_delete(context, chat_id, processing_message.message_id)
            msg = (
                "متاسفانه به دلیل محدودیت‌های ایمنی، امکان پاسخ به این سوال وجود ندارد."
                if e.blocked else
                "پاسخی دریافت نشد. لطفاً سوال خود را به شکل دیگری مطرح کنید."
            )
            await context.bot.send_message(chat_id=chat_id, text=msg)
            return True
        except ai_service.AIServiceUnavailable as e:
            await _safe_delete(context, chat_id, processing_message.message_id)
            await context.bot.send_message(chat_id=chat_id, text=messages.AI_UNAVAILABLE)
            await error_reporting.report_service_issue(
                context, str(e), context_label="/ask", failure_feature="ai", user_id=user_id,
            )
            return True

        if not is_admin(user_id):
            await ai_usage_repository.increment_ai_usage(user_id)
        await feature_usage_repository.log_usage(user_id, "ai", detail=model_used)
        await _safe_delete(context, chat_id, processing_message.message_id)

        # پیش‌نمایش تدریجی (Bot API 9.5+، فقط چت خصوصی) — کاملاً افزوده،
        # روی هر مانع (چت گروهی، فلگ config، هر خطای واقعی API) بی‌سروصدا
        # False برمی‌گردونه و همون مسیر همیشگی زیر بدون تغییر اجرا می‌شه؛
        # پیام نهاییِ persist‌شده مستقل از نتیجه‌ی پیش‌نمایش همیشه ارسال
        # می‌شه.
        await stream_preview(context.bot, chat_id, full_text, is_private_chat)

        async def send_fn(chunk, parse_mode):
            await context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode=parse_mode)

        await _send_reply_chunks(send_fn, full_text, bot=context.bot, chat_id=chat_id)
        return True

    except Exception as e:
        await _report_unexpected_error(
            context, e, command_name="ask", chat_id=chat_id, user_id=user_id,
        )
        return True


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.message.from_user.id
    if not is_admin(admin_id):
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.text:
        await context.bot.send_message(
            chat_id=admin_id,
            text="لطفاً این دستور را در پاسخ به یک پیام متنی استفاده کنید.",
        )
        return

    user_question = update.message.reply_to_message.text
    original_message = update.message.reply_to_message

    if not await _require_ai_key_configured(context, admin_id, context_label="/ai", user_id=admin_id):
        return

    try:
        system_prompt = _admin_system_prompt()
        try:
            full_text, _model_used = await ai_service.ask(user_question, system_prompt)
        except ai_service.AIResponseEmpty:
            await context.bot.send_message(
                chat_id=admin_id,
                text="پاسخی دریافت نشد (احتمالاً فیلتر ایمنی).",
            )
            return
        except ai_service.AIServiceUnavailable as e:
            await context.bot.send_message(chat_id=admin_id, text=messages.AI_UNAVAILABLE)
            await error_reporting.report_service_issue(
                context, str(e), context_label="/ai", failure_feature="ai", user_id=admin_id,
            )
            return

        async def send_fn(chunk, parse_mode):
            await original_message.reply_text(text=chunk, parse_mode=parse_mode)

        await _send_reply_chunks(
            send_fn, full_text,
            bot=context.bot, chat_id=admin_id, reply_to_message_id=original_message.message_id,
        )

    except Exception as e:
        await _report_unexpected_error(
            context, e, command_name="ai", chat_id=admin_id, user_id=admin_id,
        )


async def handle_ai_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if is_admin(user_id):
        context.user_data["awaiting_ai_question"] = True
        await update.message.reply_text("لطفا سوال خود را از هوش مصنوعی بپرسید:")
        return

    can_ask, message = await ai_usage_repository.check_ai_limit(user_id)
    if can_ask:
        context.user_data["awaiting_ai_question"] = True
        await update.message.reply_text("لطفا سوال خود را از هوش مصنوعی بپرسید:")
    else:
        await update.message.reply_text(f"⚠️ {message}")


async def handle_ai_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question_text = update.message.text
    context.user_data["ai_question_text"] = question_text
    context.user_data["awaiting_ai_question"] = False

    keyboard = [[
        InlineKeyboardButton("✅ تایید و ارسال", callback_data="ai_confirm_send"),
        InlineKeyboardButton("✏️ ویرایش", callback_data="ai_edit_question"),
    ]]
    await update.message.reply_text(
        text=f'❓سوال شما:\n\n "{question_text}"\n\nآیا تایید می‌کنید؟',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_ai_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    user_id = query.from_user.id
    chat_id = update.effective_chat.id

    if data == "ai_confirm_send":
        try:
            await query.answer("در حال ارسال سوال...")
        except Exception:
            pass

        question = context.user_data.get("ai_question_text", "سوال یافت نشد.")
        processed = await ask_user_question(
            context, chat_id, question, user_id,
            is_private_chat=update.effective_chat.type == ChatType.PRIVATE,
        )

        try:
            if processed:
                await query.edit_message_text(
                    "✅ سوال شما برای پردازش ارسال شد. لطفاً منتظر پاسخ بمانید...",
                )
            else:
                await query.delete_message()
        except Exception as e:
            logger.debug("ai_confirm_send cleanup: %s", e)

    elif data == "ai_edit_question":
        try:
            await query.answer()
        except Exception:
            pass
        try:
            await query.edit_message_text("لطفا سوال جدید خود را بنویسید:")
        except Exception:
            pass

        if is_admin(user_id):
            context.user_data["awaiting_ai_question"] = True
            await context.bot.send_message(
                chat_id=chat_id, text="لطفا سوال خود را از هوش مصنوعی بپرسید:",
            )
            return

        can_ask, message = await ai_usage_repository.check_ai_limit(user_id)
        if can_ask:
            context.user_data["awaiting_ai_question"] = True
            await context.bot.send_message(
                chat_id=chat_id, text="لطفا سوال خود را از هوش مصنوعی بپرسید:",
            )
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ {message}")