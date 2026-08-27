# src/bme_bot/handlers/maintenance_admin_edit.py
#
# فاز M1: مدیریت بخش «تعمیرات و نگهداری» توسط
# ادمین — فعال/غیرفعال‌کردن per-device + افزودن/پاک‌کردن محتوای هر زیربخش.
#
# چرا یک منوی صریح (state-machine چندمرحله‌ای)، نه یک حلقه‌ی ضمنی؟
# طرح اولیه («بفرست تا بگی تمومه») رد شد چون ادمین همیشه دقیقاً نمی‌دانست در
# چه مرحله‌ای است. اینجا هر پیام یک «صفحه»ی روشن با دکمه‌های مشخص است: صفحه‌ی
# فهرست ۴ زیربخش (با تعداد آیتم فعلی جلوی هرکدوم) → صفحه‌ی مدیریت یک زیربخش
# (افزودن متن/عکس/ویدیو، پاک‌کردن، بازگشت) → پرامپت صریح موقع افزودن → تایید و
# بازگشت به همان صفحه با شمارش به‌روز.
#
# --- طراحی state ---
# تقریباً همه‌ی پیمایش (انتخاب زیربخش، افزودن، پاک‌کردن، toggle، خروج) در یک
# state واحد (MENU) زندگی می‌کند، چون هیچ‌کدام منتظر پیام متنی/رسانه‌ای از
# ادمین نیستند — فقط تپ روی دکمه. سه state جدا فقط برای «منتظر پیام واقعی
# هستیم» لازم است: AWAITING_TEXT/AWAITING_PHOTO/AWAITING_VIDEO.
#
# نکته‌ی حیاتی (هم‌الگو با equipment_admin_edit.py): این ConversationHandler
# باید *پیش از* CallbackQueryHandler(callback_handler) عمومی در app.py ثبت
# شود، وگرنه دکمه‌های این فیچر هیچ‌وقت به این‌جا نمی‌رسند.
#
# --- چرا «بازگشت به دستگاه» یک callback_data اختصاصی (maint_admin_exit) است،
# نه استفاده‌ی مجدد از callback_data خام دستگاه؟
# اگر دکمه‌ی بازگشت مستقیماً از callback_data برابر خودِ نام دستگاه استفاده
# می‌کرد (که equipment_callbacks.route عمومی آن را می‌فهمد)، تا وقتی این
# ConversationHandler هنوز به‌صورت فعال باز است (END نشده)، PTB آن تپ را به
# هندلر عمومی پایین‌تر عبور می‌داد و صفحه‌ی دستگاه درست نمایش داده می‌شد، ولی
# خودِ این ConversationHandler هرگز END نمی‌شد — دفعه‌ی بعد که ادمین دوباره
# روی «مدیریت تعمیرات» بزند، چون کلید مکالمه (chat,user) هنوز در state قبلی
# «گیر کرده»، الگوی ورودی (entry_points) دوباره چک نمی‌شود و دکمه بی‌اثر
# می‌ماند. راه‌حل: یک callback_data اختصاصی (maint_admin_exit) که *داخل خودِ*
# این ConversationHandler صریحاً صفحه‌ی ۸-دکمه‌ای دستگاه را دوباره می‌سازد و
# بعد ConversationHandler.END برمی‌گرداند — چرخه همیشه تمیز بسته می‌شود.

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from .. import maintenance_catalog
from ..db import admin_actions_repository, maintenance_repository
from ..keyboards import menu_builder
from ..utils.admin import is_admin
from ..utils.button_style import DANGER, styled_button
from . import maintenance_callbacks

logger = logging.getLogger(__name__)

MENU = "maint_admin_menu"
AWAITING_TEXT = "maint_admin_awaiting_text"
AWAITING_PHOTO = "maint_admin_awaiting_photo"
AWAITING_VIDEO = "maint_admin_awaiting_video"

_CONVERSATION_TIMEOUT_SECONDS = 300

_VALID_CONTENT_TYPES = frozenset({"text", "photo", "video"})

_ADD_PROMPTS = {
    "text": "متن این آیتم رو بفرستید (یا /cancel برای انصراف):",
    "photo": "عکس رو بفرستید؛ می‌تونید کپشن هم اضافه کنید (یا /cancel):",
    "video": "ویدیو رو بفرستید؛ می‌تونید کپشن هم اضافه کنید (یا /cancel):",
}


def _not_found_alert(query):
    return query.answer("اطلاعاتی یافت نشد.", show_alert=True)


async def _render_device_menu_text(device: str) -> tuple[str, InlineKeyboardMarkup]:
    enabled = await maintenance_repository.is_enabled(device)
    counts = await maintenance_repository.get_item_counts(device)

    status_text = "فعال ✅" if enabled else "غیرفعال ❌"
    text = f"🔧 مدیریت تعمیرات و نگهداری — {device}\n\nوضعیت: {status_text}"

    rows = [[
        InlineKeyboardButton(
            "غیرفعال‌کردن" if enabled else "فعال‌کردن",
            callback_data=f"maint_admin_toggle:{device}",
        )
    ]]
    for item_key, label in maintenance_catalog.MAINTENANCE_ITEMS:
        count = counts.get(item_key, 0)
        rows.append([
            InlineKeyboardButton(
                f"{label} ({count} آیتم)" if count else f"{label} (خالی)",
                callback_data=f"maint_admin_item:{device}:{item_key}",
            )
        ])
    rows.append([InlineKeyboardButton("⬅️ بازگشت به دستگاه", callback_data=f"maint_admin_exit:{device}")])

    return text, InlineKeyboardMarkup(rows)


async def _render_item_menu_text(device: str, item_key: str) -> tuple[str, InlineKeyboardMarkup]:
    items = await maintenance_repository.get_items(device, item_key)
    label = maintenance_catalog.get_label(item_key)

    text = f"«{label}» — دستگاه: {device}\n\nتعداد آیتم فعلی: {len(items)}"

    rows = [
        [InlineKeyboardButton("➕ افزودن متن", callback_data=f"maint_admin_add:{device}:{item_key}:text")],
        [InlineKeyboardButton("➕ افزودن عکس", callback_data=f"maint_admin_add:{device}:{item_key}:photo")],
        [InlineKeyboardButton("➕ افزودن ویدیو", callback_data=f"maint_admin_add:{device}:{item_key}:video")],
    ]
    if items:
        rows.append([
            styled_button(
                "🗑 پاک‌کردن این زیربخش", DANGER, callback_data=f"maint_admin_clear_ask:{device}:{item_key}",
            )
        ])
    rows.append([
        InlineKeyboardButton("⬅️ بازگشت به فهرست زیربخش‌ها", callback_data=f"maint_admin_open:{device}")
    ])

    return text, InlineKeyboardMarkup(rows)


async def start_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ورودی: تپ روی «🔧 مدیریت تعمیرات و نگهداری»، یا بازگشت از یک زیربخش.
    callback_data: maint_admin_open:{device}."""
    query = update.callback_query
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer("شما اجازه‌ی دسترسی به این بخش را ندارید.", show_alert=True)
        return ConversationHandler.END

    _, device = query.data.split(":", 1)
    if not menu_builder.is_device(device):
        await _not_found_alert(query)
        return ConversationHandler.END

    await query.answer()
    text, markup = await _render_device_menu_text(device)
    try:
        await query.edit_message_text(text=text, reply_markup=markup)
    except Exception as e:
        logger.debug("maint_admin_open edit failed device=%s: %s", device, e)
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=markup)

    return MENU


async def toggle_enabled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    _, device = query.data.split(":", 1)
    if not menu_builder.is_device(device):
        await _not_found_alert(query)
        return ConversationHandler.END

    currently_enabled = await maintenance_repository.is_enabled(device)
    await maintenance_repository.set_enabled(device, not currently_enabled)
    await admin_actions_repository.log_action(
        update.effective_user.id,
        "toggle_maintenance",
        target=f"{device}:{'off' if currently_enabled else 'on'}",
    )

    await query.answer("✅ به‌روزرسانی شد.")
    text, markup = await _render_device_menu_text(device)
    await query.edit_message_text(text=text, reply_markup=markup)
    return MENU


async def show_item_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """callback_data: maint_admin_item:{device}:{item_key}."""
    query = update.callback_query
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await _not_found_alert(query)
        return ConversationHandler.END
    _, device, item_key = parts

    if not menu_builder.is_device(device) or item_key not in maintenance_catalog.ITEM_KEYS:
        await _not_found_alert(query)
        return ConversationHandler.END

    await query.answer()
    text, markup = await _render_item_menu_text(device, item_key)
    await query.edit_message_text(text=text, reply_markup=markup)
    return MENU


async def start_add_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """callback_data: maint_admin_add:{device}:{item_key}:{content_type}."""
    query = update.callback_query
    parts = query.data.split(":", 3)
    if len(parts) != 4:
        await _not_found_alert(query)
        return ConversationHandler.END
    _, device, item_key, content_type = parts

    if (
        not menu_builder.is_device(device)
        or item_key not in maintenance_catalog.ITEM_KEYS
        or content_type not in _VALID_CONTENT_TYPES
    ):
        await _not_found_alert(query)
        return ConversationHandler.END

    await query.answer()
    label = maintenance_catalog.get_label(item_key)
    await query.edit_message_text(
        text=f"در حال افزودن آیتم برای «{device} / {label}».\n\n{_ADD_PROMPTS[content_type]}"
    )

    context.user_data["maint_admin_pending"] = {
        "device": device,
        "item_key": item_key,
        "content_type": content_type,
        "chat_id": query.message.chat_id,
        "message_id": query.message.message_id,
    }
    return {"text": AWAITING_TEXT, "photo": AWAITING_PHOTO, "video": AWAITING_VIDEO}[content_type]


async def _save_and_return_to_item_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, text_content: str | None, file_id: str | None,
) -> int:
    pending = context.user_data.get("maint_admin_pending")
    if not pending:
        await update.message.reply_text("خطای داخلی — لطفاً دوباره از روی «🔧 مدیریت تعمیرات» شروع کنید.")
        return ConversationHandler.END

    device, item_key, content_type = pending["device"], pending["item_key"], pending["content_type"]
    await maintenance_repository.add_item(device, item_key, content_type, text_content, file_id)
    await admin_actions_repository.log_action(
        update.effective_user.id, "add_maintenance_item", target=f"{device}:{item_key}:{content_type}",
    )
    context.user_data.pop("maint_admin_pending", None)

    await update.message.reply_text("✅ ذخیره شد.")

    text, markup = await _render_item_menu_text(device, item_key)
    try:
        await context.bot.edit_message_text(
            chat_id=pending["chat_id"], message_id=pending["message_id"], text=text, reply_markup=markup,
        )
    except Exception as e:
        logger.warning("Could not refresh item menu after add: %s", e)
        await context.bot.send_message(chat_id=pending["chat_id"], text=text, reply_markup=markup)

    return MENU


async def receive_text_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _save_and_return_to_item_menu(update, context, text_content=update.message.text, file_id=None)


async def receive_photo_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    photo = update.message.photo[-1]
    return await _save_and_return_to_item_menu(
        update, context, text_content=update.message.caption, file_id=photo.file_id,
    )


async def receive_video_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    video = update.message.video
    return await _save_and_return_to_item_menu(
        update, context, text_content=update.message.caption, file_id=video.file_id,
    )


async def remind_text_needed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفاً متن مدنظرتون رو بفرستید، یا /cancel بزنید.")


async def remind_photo_needed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفاً یه عکس بفرستید، یا /cancel بزنید.")


async def remind_video_needed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفاً یه ویدیو بفرستید، یا /cancel بزنید.")


async def ask_clear_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """callback_data: maint_admin_clear_ask:{device}:{item_key}."""
    query = update.callback_query
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await _not_found_alert(query)
        return ConversationHandler.END
    _, device, item_key = parts

    if not menu_builder.is_device(device) or item_key not in maintenance_catalog.ITEM_KEYS:
        await _not_found_alert(query)
        return ConversationHandler.END

    items = await maintenance_repository.get_items(device, item_key)
    label = maintenance_catalog.get_label(item_key)

    await query.answer()
    await query.edit_message_text(
        text=(
            f"⚠️ مطمئنید می‌خواید همه‌ی {len(items)} آیتم «{label}» رو پاک کنید؟\n"
            "این عمل قابل بازگشت نیست."
        ),
        reply_markup=InlineKeyboardMarkup([
            [styled_button("بله، پاک کن", DANGER, callback_data=f"maint_admin_clear_do:{device}:{item_key}")],
            [InlineKeyboardButton("انصراف", callback_data=f"maint_admin_clear_no:{device}:{item_key}")],
        ]),
    )
    return MENU


async def do_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """callback_data: maint_admin_clear_do:{device}:{item_key}."""
    query = update.callback_query
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await _not_found_alert(query)
        return ConversationHandler.END
    _, device, item_key = parts

    if not menu_builder.is_device(device) or item_key not in maintenance_catalog.ITEM_KEYS:
        await _not_found_alert(query)
        return ConversationHandler.END

    await maintenance_repository.clear_item(device, item_key)
    await admin_actions_repository.log_action(
        update.effective_user.id, "clear_maintenance_item", target=f"{device}:{item_key}",
    )

    await query.answer("✅ پاک شد.")
    text, markup = await _render_item_menu_text(device, item_key)
    await query.edit_message_text(text=text, reply_markup=markup)
    return MENU


async def cancel_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """callback_data: maint_admin_clear_no:{device}:{item_key}."""
    query = update.callback_query
    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await _not_found_alert(query)
        return ConversationHandler.END
    _, device, item_key = parts

    if not menu_builder.is_device(device) or item_key not in maintenance_catalog.ITEM_KEYS:
        await _not_found_alert(query)
        return ConversationHandler.END

    await query.answer()
    text, markup = await _render_item_menu_text(device, item_key)
    await query.edit_message_text(text=text, reply_markup=markup)
    return MENU


async def exit_to_device(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """callback_data: maint_admin_exit:{device}. بازگشت به صفحه‌ی ۸-دکمه‌ای
    دستگاه، با همان دکمه‌ی «مدیریت تعمیرات» که maintenance_callbacks.with_maintenance_button
    برای ادمین اضافه می‌کند (تا از همین‌جا دوباره بشود وارد این مکالمه شد)."""
    query = update.callback_query
    _, device = query.data.split(":", 1)
    context.user_data.pop("maint_admin_pending", None)

    if not menu_builder.is_device(device):
        await _not_found_alert(query)
        return ConversationHandler.END

    line = menu_builder.get_device_line(device)
    reply_markup = menu_builder.get_device_detail_markup(device, line)
    reply_markup = await maintenance_callbacks.with_maintenance_button(
        reply_markup, device, update.effective_user.id,
    )

    await query.answer()
    try:
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    except Exception as e:
        logger.debug("maint_admin_exit markup refresh failed device=%s: %s", device, e)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("maint_admin_pending", None)
    await update.message.reply_text("لغو شد.")
    return ConversationHandler.END


async def handle_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هم‌الگو با equipment_admin_edit.handle_edit_timeout."""
    context.user_data.pop("maint_admin_pending", None)
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ زمان مدیریت تعمیرات تمام شد. برای شروع دوباره روی «🔧 مدیریت تعمیرات و نگهداری» بزنید.",
        )


maintenance_admin_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_admin_menu, pattern=r"^maint_admin_open:")],
    states={
        MENU: [
            CallbackQueryHandler(start_admin_menu, pattern=r"^maint_admin_open:"),
            CallbackQueryHandler(toggle_enabled, pattern=r"^maint_admin_toggle:"),
            CallbackQueryHandler(show_item_menu, pattern=r"^maint_admin_item:"),
            CallbackQueryHandler(start_add_item, pattern=r"^maint_admin_add:"),
            CallbackQueryHandler(ask_clear_confirm, pattern=r"^maint_admin_clear_ask:"),
            CallbackQueryHandler(do_clear, pattern=r"^maint_admin_clear_do:"),
            CallbackQueryHandler(cancel_clear, pattern=r"^maint_admin_clear_no:"),
            CallbackQueryHandler(exit_to_device, pattern=r"^maint_admin_exit:"),
        ],
        AWAITING_TEXT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text_item),
            MessageHandler(~filters.COMMAND, remind_text_needed),
        ],
        AWAITING_PHOTO: [
            MessageHandler(filters.PHOTO, receive_photo_item),
            MessageHandler(~filters.COMMAND, remind_photo_needed),
        ],
        AWAITING_VIDEO: [
            MessageHandler(filters.VIDEO, receive_video_item),
            MessageHandler(~filters.COMMAND, remind_video_needed),
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, handle_timeout)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    conversation_timeout=_CONVERSATION_TIMEOUT_SECONDS,
    name="maintenance_admin_edit",
)
