# src/bme_bot/handlers/equipment_callbacks.py
# مسیریابی درخت تجهیزات + نمایش جزئیات دستگاه.

from __future__ import annotations

import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..db import equipment_repository, feature_usage_repository
from ..keyboards import menu_builder
from ..utils.admin import is_admin
from ..utils.button_style import PRIMARY, styled_button
from ..utils.retry import async_retry
from . import maintenance_callbacks

logger = logging.getLogger(__name__)

_SOFT_UNAVAILABLE = "سرویس موقتاً در دسترس نیست. لطفاً کمی بعد دوباره تلاش کنید."


async def _safe_answer(query, text: str | None = None, *, alert: bool = False) -> None:
    """answer بی‌خطر؛ خطای query منقضی را می‌بلعد."""
    try:
        if text:
            await query.answer(text, show_alert=alert)
        else:
            await query.answer()
    except Exception:
        pass


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = menu_builder.get_main_menu_markup()
    await update.message.reply_text(text="یک گزینه را انتخاب کنید : ", reply_markup=reply_markup)


async def handle_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE, node_id: str):
    query = update.callback_query
    reply_markup = menu_builder.get_menu_markup(node_id)
    try:
        await async_retry(
            lambda: query.edit_message_reply_markup(reply_markup=reply_markup),
            label=f"menu_click:{node_id}",
        )
    except Exception as e:
        logger.warning("menu_click failed node=%s: %s", node_id, e)
        await _safe_answer(query)


async def handle_device_click(update: Update, context: ContextTypes.DEFAULT_TYPE, device: str):
    query = update.callback_query
    line = menu_builder.get_device_line(device)
    reply_markup = menu_builder.get_device_detail_markup(device, line)
    # فاز M2: دکمه‌ی «تعمیرات و نگهداری» — ادمین همیشه، کاربر عادی فقط اگر
    # این دستگاه فعال و محتوادار باشد (maintenance_callbacks.with_maintenance_button).
    reply_markup = await maintenance_callbacks.with_maintenance_button(
        reply_markup, device, update.effective_user.id,
    )
    try:
        await async_retry(
            lambda: query.edit_message_reply_markup(reply_markup=reply_markup),
            label=f"device_click:{device}",
        )
    except Exception as e:
        logger.warning("device_click failed device=%s: %s", device, e)
        await _safe_answer(query)
        return

    try:
        await feature_usage_repository.log_usage(
            update.effective_user.id, "equipment", detail=device,
        )
    except Exception as e:
        logger.warning("log_usage equipment failed: %s", e)


def with_admin_edit_button(
    reply_markup: InlineKeyboardMarkup, device: str, action: str, line: str, user_id: int,
) -> InlineKeyboardMarkup:
    if not is_admin(user_id):
        return reply_markup
    edit_row = [
        styled_button(
            "✏️ ویرایش این متن", PRIMARY,
            callback_data=f"admin_edit_field:{device}:{action}:{line}",
        )
    ]
    return InlineKeyboardMarkup(list(reply_markup.inline_keyboard) + [edit_row])


async def _send_definition_photo(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    device_info: str,
    device_photo,
    reply_markup: InlineKeyboardMarkup,
    device: str,
) -> bool:
    """ارسال عکس معرفی با retry. True = موفق."""
    try:
        await async_retry(
            lambda: context.bot.send_photo(
                chat_id=chat_id,
                caption=device_info,
                photo=device_photo,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            ),
            retries=2,
            base_delay=1.0,
            label=f"send_photo:{device}",
        )
        return True
    except Exception as e:
        logger.warning("send_photo failed device=%s: %s", device, e)
        return False


async def _show_text_action(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    device_info: str,
    reply_markup: InlineKeyboardMarkup,
    device: str,
    action: str,
) -> None:
    """ویرایش پیام؛ در صورت شکست → حذف + ارسال پیام جدید (هر دو با retry)."""
    try:
        await async_retry(
            lambda: query.edit_message_text(
                text=device_info,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            ),
            label=f"edit_text:{device}:{action}",
        )
        return
    except Exception as e:
        logger.debug("edit_message_text fallback device=%s action=%s: %s", device, action, e)

    try:
        await async_retry(lambda: query.delete_message(), retries=1, label=f"delete:{device}")
    except Exception as e:
        logger.debug("delete_message skipped device=%s: %s", device, e)

    try:
        await async_retry(
            lambda: context.bot.send_message(
                chat_id=chat_id,
                text=device_info,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            ),
            label=f"send_text:{device}:{action}",
        )
    except Exception as e:
        logger.warning("send_message failed device=%s action=%s: %s", device, action, e)
        await _safe_answer(query, _SOFT_UNAVAILABLE, alert=True)


async def handle_device_action(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    decoded = menu_builder.decode_device_action(data)
    query = update.callback_query

    if decoded is None:
        await _safe_answer(query, "درخواست نامعتبر است.", alert=True)
        return

    device, action, line = decoded
    chat_id = update.effective_chat.id

    if not menu_builder.is_device(device) or not menu_builder.is_menu(line):
        await _safe_answer(query, "اطلاعاتی یافت نشد.", alert=True)
        return

    # --- معرفی دستگاه (عکس) ---
    if action == "definition":
        result = await equipment_repository.get_definition_with_photo(device)
        if not result:
            await _safe_answer(query, "اطلاعاتی یافت نشد.", alert=True)
            return

        device_info, device_photo = result
        reply_markup = menu_builder.get_device_detail_markup(
            device, line, hide_definition_row=True,
        )
        reply_markup = with_admin_edit_button(
            reply_markup, device, action, line, update.effective_user.id,
        )

        await _safe_answer(query)

        ok = await _send_definition_photo(
            context, chat_id, device_info, device_photo, reply_markup, device,
        )
        if not ok:
            try:
                await context.bot.send_message(chat_id=chat_id, text=_SOFT_UNAVAILABLE)
            except Exception as e:
                logger.debug("soft notice failed device=%s: %s", device, e)
            return

        try:
            await async_retry(
                lambda: query.delete_message(),
                retries=1,
                label=f"delete_after_photo:{device}",
            )
        except Exception as e:
            logger.debug("delete after photo skipped device=%s: %s", device, e)
        return

    # --- سایر اکشن‌های متنی ---
    device_info = await equipment_repository.get_action_text(device, action)
    if not device_info:
        await _safe_answer(query, "اطلاعاتی برای این بخش یافت نشد.", alert=True)
        return

    reply_markup = menu_builder.get_device_detail_markup(device, line)
    reply_markup = with_admin_edit_button(
        reply_markup, device, action, line, update.effective_user.id,
    )

    await _safe_answer(query)
    await _show_text_action(
        query, context, chat_id, device_info, reply_markup, device, action,
    )


async def route(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> bool:
    """اگر data مربوط به درخت تجهیزات بود True."""
    if menu_builder.is_device(data):
        await handle_device_click(update, context, data)
        return True
    if menu_builder.decode_device_action(data) is not None:
        await handle_device_action(update, context, data)
        return True
    if menu_builder.is_menu(data):
        await handle_menu_click(update, context, data)
        return True
    return False