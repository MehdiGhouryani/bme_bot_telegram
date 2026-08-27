# src/bme_bot/handlers/maintenance_callbacks.py
#
# فاز M2: نمایش بخش «تعمیرات و نگهداری» به
# کاربر عادی. بدون ConversationHandler — کاملاً stateless، هم‌الگو با
# equipment_callbacks.handle_device_click/handle_device_action (فقط تپ روی
# دکمه، بدون هیچ ورودی متنی از کاربر لازم).
#
# چرا فایل جدا از equipment_callbacks.py؟ طبق قانون ۲ («هر فیچر فایل مستقل
# خودش»)، این یک دامنه‌ی مفهومی جداست، هرچند with_maintenance_button باید از
# equipment_callbacks.handle_device_click فراخوانی شود (نقطه‌ی اتصال حداقلی،
# دقیقاً هم‌الگو با این‌که equipment_admin_edit.py هم از equipment_callbacks
# وارد می‌کند).

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from .. import maintenance_catalog
from ..db import maintenance_repository
from ..keyboards import menu_builder
from ..utils.admin import is_admin

logger = logging.getLogger(__name__)

_NOT_FOUND_MESSAGE = "اطلاعاتی یافت نشد."


async def with_maintenance_button(
    reply_markup: InlineKeyboardMarkup, device: str, user_id: int,
) -> InlineKeyboardMarkup:
    """صفحه‌ی ۸-دکمه‌ای دستگاه: ادمین همیشه دکمه‌ی «مدیریت» می‌بیند؛ کاربر
    عادی فقط اگر تعمیرات این دستگاه فعال *و* حداقل یک آیتم داشته باشد
    (تصمیم: زیربخش/فیچر خالی اصلاً نشان داده نمی‌شود)."""
    if is_admin(user_id):
        row = [InlineKeyboardButton(
            "🔧 مدیریت تعمیرات و نگهداری", callback_data=f"maint_admin_open:{device}",
        )]
    else:
        if not await maintenance_repository.is_enabled(device):
            return reply_markup
        if not await maintenance_repository.has_any_content(device):
            return reply_markup
        row = [InlineKeyboardButton(
            "🛠 تعمیرات و نگهداری", callback_data=f"maint_view_open:{device}",
        )]

    return InlineKeyboardMarkup(list(reply_markup.inline_keyboard) + [row])


async def _show_sub_item_list(update: Update, context: ContextTypes.DEFAULT_TYPE, device: str) -> None:
    query = update.callback_query
    populated_keys = await maintenance_repository.get_populated_item_keys(device)
    if not populated_keys:
        await query.answer(_NOT_FOUND_MESSAGE, show_alert=True)
        return

    rows = [
        [InlineKeyboardButton(
            maintenance_catalog.get_label(item_key),
            callback_data=f"maint_view_item:{device}:{item_key}",
        )]
        for item_key in populated_keys
    ]
    rows.append([InlineKeyboardButton("⬅️ بازگشت به دستگاه", callback_data=device)])

    await query.answer()
    try:
        await query.edit_message_text(
            text=f"🛠 تعمیرات و نگهداری — {device}\n\nیه زیربخش رو انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
    except Exception as e:
        logger.debug("maint_view_open edit failed device=%s: %s", device, e)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"🛠 تعمیرات و نگهداری — {device}\n\nیه زیربخش رو انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(rows),
        )


async def _send_item(context: ContextTypes.DEFAULT_TYPE, chat_id: int, item: tuple) -> None:
    content_type, text_content, file_id = item
    if content_type == "text":
        await context.bot.send_message(chat_id=chat_id, text=text_content or "")
    elif content_type == "photo":
        await context.bot.send_photo(chat_id=chat_id, photo=file_id, caption=text_content or None)
    elif content_type == "video":
        await context.bot.send_video(chat_id=chat_id, video=file_id, caption=text_content or None)


async def _show_items(update: Update, context: ContextTypes.DEFAULT_TYPE, device: str, item_key: str) -> None:
    query = update.callback_query
    items = await maintenance_repository.get_items(device, item_key)
    if not items:
        await query.answer(_NOT_FOUND_MESSAGE, show_alert=True)
        return

    await query.answer()
    chat_id = query.message.chat_id
    for item in items:
        try:
            await _send_item(context, chat_id, item)
        except Exception as e:
            logger.warning("Failed to send maintenance item device=%s item_key=%s: %s", device, item_key, e)

    await context.bot.send_message(
        chat_id=chat_id,
        text="⬅️ برای بازگشت بزنید:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ بازگشت به دستگاه", callback_data=device)
        ]]),
    )


async def route(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    query = update.callback_query

    if data.startswith("maint_view_item:"):
        parts = data.split(":", 2)
        if len(parts) != 3:
            await query.answer(_NOT_FOUND_MESSAGE, show_alert=True)
            return
        _, device, item_key = parts
        if not menu_builder.is_device(device) or item_key not in maintenance_catalog.ITEM_KEYS:
            await query.answer(_NOT_FOUND_MESSAGE, show_alert=True)
            return
        await _show_items(update, context, device, item_key)
        return

    if data.startswith("maint_view_open:"):
        _, device = data.split(":", 1)
        if not menu_builder.is_device(device):
            await query.answer(_NOT_FOUND_MESSAGE, show_alert=True)
            return
        await _show_sub_item_list(update, context, device)
        return

    await query.answer(_NOT_FOUND_MESSAGE, show_alert=True)
