# src/bme_bot/handlers/global_gate.py
#
# دروازه‌ی سراسری. membership_required فقط دور button_click/callback_handler
# است — CommandHandler("ask"...)، CommandHandler("ai"...)، CommandHandler("start"...)،
# و MessageHandler عکس OCR هرکدام مستقل ثبت شده‌اند و از آن عبور نمی‌کنند.
# یعنی اگر «بن» را فقط داخل membership_required بگذاریم، کاربر بن‌شده همچنان
# می‌تواند از این ۴ مسیر استفاده کند — بن ناقص می‌شود.
#
# رفع طبق الگوی رسمی مستندشده‌ی خودِ python-telegram-bot (ویکی «Frequently
# requested design patterns»): یک TypeHandler که در پایین‌ترین گروه ثبت
# می‌شود (باید *قبل* از همه‌ی گروه‌های دیگر اجرا شود؛ در app.py با
# app.add_handler(TypeHandler(Update, ...), group=-1) ثبت می‌شود) و با
# raise کردن ApplicationHandlerStop، از رسیدن آپدیت به *هر* handler دیگری
# (صرف‌نظر از گروه) جلوگیری می‌کند. همین مکانیزم برای ردیابی last_seen_at هم
# استفاده می‌شود — چون این تنها نقطه‌ای است که تضمین می‌کند برای *هر* تعامل
# (نه فقط آن‌هایی که از button_click/callback_handler رد می‌شوند) اجرا می‌شود.

import logging

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from ..db import users_repository

logger = logging.getLogger(__name__)

_BANNED_MESSAGE = "⛔ شما توسط ادمین مسدود شده‌اید و امکان استفاده از ربات را ندارید."


async def enforce_ban_and_track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """باید در پایین‌ترین گروه (group=-1 یا کمتر) ثبت شود تا پیش از همه‌ی
    handler های دیگر اجرا شود."""
    user = update.effective_user
    if not user:
        return

    if await users_repository.is_banned(user.id):
        try:
            if update.callback_query:
                await update.callback_query.answer(_BANNED_MESSAGE, show_alert=True)
            elif update.effective_chat:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=_BANNED_MESSAGE)
        except Exception:
            logger.exception("ارسال پیام «مسدود شده‌اید» به کاربر %s شکست خورد.", user.id)

        # پیام روشن، نه سکوت. صرف‌نظر از موفقیت ارسال پیام بالا، پردازش
        # آپدیت باید همیشه همین‌جا متوقف شود.
        raise ApplicationHandlerStop

    await users_repository.touch_last_seen(user.id)
