# src/bme_bot/handlers/membership.py
# بررسی عضویت در گروه؛ در صورت خطای API هیچ پیامی به کاربر نشان داده نمی‌شود.

from __future__ import annotations

import asyncio
import logging
from functools import wraps

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .. import config

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRY_DELAY = 0.6
_MEMBER_STATUSES = frozenset({"member", "administrator", "creator"})


def send_join_request(update: Update):
    keyboard = [
        [InlineKeyboardButton("عضویت در گروه", url=f"https://t.me/{config.GROUP_CHAT_ID[1:]}")],
        [InlineKeyboardButton("✅ عضو شدم (دوباره امتحان کنید)", callback_data="check_membership")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "🔔 برای استفاده از این بخش، باید عضو گروه دانشجویان باشید!"

    if update.callback_query:
        return update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    return update.message.reply_text(text, reply_markup=reply_markup)


async def _get_membership_status(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str | None:
    """status را برمی‌گرداند؛ در صورت شکست موقت None (بدون ارسال پیام به کاربر)."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            member = await context.bot.get_chat_member(
                chat_id=config.GROUP_CHAT_ID, user_id=user_id,
            )
            return member.status
        except Exception as e:
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "membership check user=%s attempt=%d/%d failed: %s",
                    user_id, attempt + 1, _MAX_RETRIES + 1, e,
                )
                await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
                continue
            logger.warning("membership check user=%s exhausted retries: %s", user_id, e)
    return None


def membership_required(func):
    """اگر عضو نبود → درخواست عضویت؛ اگر API خطا داد → سکوت (بدون پیام خطا)."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        status = await _get_membership_status(context, user.id)

        if status is None:
            # خطای شبکه/timeout — به کاربر چیزی نمی‌گوییم؛ فقط callback را بی‌صدا می‌بندیم.
            if update.callback_query:
                try:
                    await update.callback_query.answer()
                except Exception:
                    pass
            return

        if status in _MEMBER_STATUSES:
            return await func(update, context, *args, **kwargs)

        await send_join_request(update)

    return wrapper


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه «عضو شدم» — در صورت خطای API هیچ alert خطایی نشان داده نمی‌شود."""
    from .start import start

    query = update.callback_query
    user = query.from_user

    status = await _get_membership_status(context, user.id)

    if status is None:
        try:
            await query.answer()  # بی‌صدا؛ بدون متن خطا
        except Exception:
            pass
        return

    if status in _MEMBER_STATUSES:
        try:
            await query.answer("عضویت شما تایید شد. خوش آمدید!", show_alert=True)
        except Exception:
            pass
        try:
            await query.delete_message()
        except Exception:
            pass
        await start(update, context)
        return

    try:
        await query.answer("شما هنوز عضو گروه نیستید. لطفاً ابتدا عضو شوید.", show_alert=True)
    except Exception:
        pass