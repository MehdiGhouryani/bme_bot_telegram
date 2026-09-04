# src/bme_bot/handlers/equipment_admin_edit.py
#
# امکان ویرایش متن اطلاعات دستگاه توسط ادمین، مستقیم از داخل تلگرام — بدون
# دست‌زدن مستقیم به دیتابیس. دکمه‌ی ✏️
# (equipment_callbacks.with_admin_edit_button) فقط برای ادمین و فقط روی صفحه‌ی
# نمایش خودِ متن (نه گرید اصلی ۷-اکشنی) ظاهر می‌شود.
#
# چرا یک فایل جدا، نه داخل admin.py: این فیچر مفهوماً به دامنه‌ی تجهیزات
# (equipment_callbacks/equipment_repository) نزدیک‌تر است تا به دامنه‌ی
# admin.py (مدیریت کاربر/Broadcast/سلامت سیستم). همان الگوی ConversationHandler
# رسمی PTB که admin.py استفاده می‌کند اینجا هم تکرار شده — برای یکدستی، و چون
# همان مزایا (state تمیز، conversation_timeout رایگان) صدق می‌کند.
#
# *** نکته‌ی حیاتی برای ثبت در app.py ***
# این ConversationHandler باید *پیش از* CallbackQueryHandler(callback_handler)
# عمومی ثبت شود — دقیقاً همان الزامی که admin.py برای دو ConversationHandler
# خودش رعایت می‌کند: callback_handler عمومی از طریق equipment_callbacks.route
# ابتدا menu_builder.decode_device_action(data) را چک می‌کند، که یک split با
# دو جداکننده‌ی ':' است — یعنی برای "admin_edit_field:device:action:line" هم
# بدون خطا (اشتباهاً) یک tuple سه‌تایی برمی‌گرداند. اگر این ConversationHandler
# دیرتر ثبت شود، callback_handler زودتر آن را (نادرست) به‌عنوان یک کلیک روی
# دستگاه/اکشن جزئیات پردازش می‌کند و دکمه‌ی ✏️ عملاً کار نمی‌کند.

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from ..db import admin_actions_repository, equipment_repository
from ..keyboards import menu_builder
from ..utils.admin import is_admin
from ..utils.text_chunking import utf16_len
from . import equipment_callbacks

logger = logging.getLogger(__name__)

AWAITING_NEW_TEXT = "equipment_edit_awaiting_text"

# بدون JobQueue فعال (python-telegram-bot[job-queue] extra)، این پارامتر
# بی‌اثر می‌ماند.
_CONVERSATION_TIMEOUT_SECONDS = 300

# سقف کپشن عکس در تلگرام. اکشن "definition" برخلاف بقیه‌ی اکشن‌های متنی (که
# با edit_message_text/۴۰۹۶ کاراکتر نمایش داده می‌شوند)، تنها اکشنیه که در
# equipment_callbacks._send_definition_photo به‌شکل کپشن یک عکس برای همه‌ی
# کاربران ارسال می‌شود — و کپشن تلگرام سقفش ۱۰۲۴ کاراکتره، نه ۴۰۹۶. بدون این
# چک، ذخیره‌ی یک معرفی طولانی‌تر این‌جا «موفق» به نظر می‌رسه ولی از همون لحظه
# send_photo برای همه‌ی کاربران با خطا مواجه می‌شه و صفحه‌ی معرفی اون دستگاه
# به‌جای محتوا فقط پیام «سرویس موقتاً در دسترس نیست» نشون می‌ده — بی‌صدا، تا
# کسی متوجه بشه.
_DEFINITION_CAPTION_MAX_LENGTH = 1024


async def start_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ورودی: تپ روی ✏️. callback_data به‌شکل admin_edit_field:device:action:line."""
    query = update.callback_query
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer("شما اجازه‌ی دسترسی به این بخش را ندارید.", show_alert=True)
        return ConversationHandler.END

    parts = query.data.split(":", 3)
    if len(parts) != 4:
        await query.answer("فرمت درخواست نامعتبر است.", show_alert=True)
        return ConversationHandler.END
    _, device, action, line = parts

    # اعتبارسنجی: device باید واقعاً در درخت باشد، action باید در همان
    # allow-list ای باشد که equipment_repository برای SELECT/UPDATE استفاده
    # می‌کند — همان دلیل امنیتی بند ۳.۱، این‌جا هم صدق می‌کند.
    if not menu_builder.is_device(device) or action not in equipment_repository.ALLOWED_ACTIONS:
        await query.answer("اطلاعاتی یافت نشد.", show_alert=True)
        return ConversationHandler.END

    await query.answer()

    current_text = await equipment_repository.get_action_text(device, action)
    context.user_data["equipment_edit"] = {
        "device": device,
        "action": action,
        "line": line,
        "chat_id": query.message.chat_id,
        "message_id": query.message.message_id,
    }

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"در حال ویرایش «{device} / {action}».\n\n"
            f"متن فعلی:\n{current_text or '(خالی)'}\n\n"
            "متن جدید را بفرستید، یا /cancel برای انصراف."
        ),
    )
    return AWAITING_NEW_TEXT


async def receive_new_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    edit_state = context.user_data.get("equipment_edit")
    if not edit_state:
        # نباید عملاً پیش بیاید (state فقط با start_edit ست می‌شود)، ولی یک
        # محافظ دفاعی ارزان است — بهتر از AttributeError خام.
        await update.message.reply_text("خطای داخلی — لطفاً دوباره از روی ✏️ شروع کنید.")
        return ConversationHandler.END

    device, action, line = edit_state["device"], edit_state["action"], edit_state["line"]
    new_text = update.message.text
    # utf16_len، نه len() خام: سقف واقعی کپشن تلگرام بر پایه‌ی UTF-16
    # code unit است، نه تعداد کاراکتر پایتون — یه متنِ کمتر از ۱۰۲۴ از
    # نظر len() که چند ایموجی خارج از BMP هم داشته باشه، می‌تونه واقعاً
    # بیشتر از سقف واقعی تلگرام باشه (رجوع به توضیح در utils/text_chunking.py).
    new_text_length = utf16_len(new_text)

    if action == "definition" and new_text_length > _DEFINITION_CAPTION_MAX_LENGTH:
        await update.message.reply_text(
            "⚠️ متن «معرفی» به‌عنوان کپشن عکس برای کاربران نمایش داده می‌شود و تلگرام "
            f"کپشن عکس را حداکثر {_DEFINITION_CAPTION_MAX_LENGTH} کاراکتر می‌پذیرد "
            f"(متن شما {new_text_length} کاراکتر است). لطفاً کوتاه‌ترش کنید و دوباره "
            "بفرستید، یا /cancel برای انصراف."
        )
        return AWAITING_NEW_TEXT

    # اعتبارسنجی مارک‌داون *قبل* از ذخیره: equipment_callbacks بعداً همین
    # متن رو با parse_mode=ParseMode.MARKDOWN به کاربرهای واقعی نشون
    # می‌ده. اگه اینجا یه `*`/`_`/`` ` `` بدون جفت باشه، تلگرام parse رو رد
    # می‌کنه — و چون هم edit_message_text هم fallback (حذف+ارسال دوباره)
    # هر دو از همین متن استفاده می‌کنن، کل این بخش برای *همه‌ی کاربران* تا
    # ویرایش بعدی از کار می‌افته، بی‌سروصدا (فقط «اطلاعاتی یافت نشد»). به‌جای
    # اینکه بعداً کشف بشه، همین‌جا با یه پیش‌نمایش واقعی (همون parse_mode)
    # چک می‌کنیم؛ اگه موفق شد، همون پیام پیش‌نمایش جای تاییدیه‌ی جدا رو هم
    # می‌گیره.
    try:
        await update.message.reply_text(
            f"✅ ذخیره شد. این متن دقیقاً همین‌طوری به کاربرها نشون داده می‌شه:\n\n{new_text}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except BadRequest as e:
        await update.message.reply_text(
            "⚠️ این متن فرمت مارک‌داون معتبری نداره (مثلاً یه `*`، `_` یا `` ` `` بدون "
            "جفتش) — دقیقاً همین چیزی بود که می‌تونست بعداً این بخش رو برای همه‌ی "
            "کاربران خراب کنه. لطفاً تصحیحش کنید و دوباره بفرستید، یا /cancel برای انصراف.\n\n"
            f"جزئیات فنی: {e}"
        )
        return AWAITING_NEW_TEXT

    await equipment_repository.update_action_text(device, action, new_text)
    await admin_actions_repository.log_action(
        update.effective_user.id, "edit_equipment_field", target=f"{device}:{action}",
    )
    context.user_data.pop("equipment_edit", None)

    # تلاش برای زنده‌کردن همان پیامی که ادمین رویش ✏️ زده بود — اگر شکست
    # بخورد (پیام خیلی قدیمی/حذف‌شده/۴۸ ساعت گذشته و تلگرام دیگر اجازه‌ی ویرایش
    # نمی‌دهد)، اهمیتی ندارد: پیام تاییدیه‌ی بالا already ارسال شده، ادمین
    # می‌داند ذخیره موفق بوده، فقط منظره‌ی صفحه‌ی قبلی به‌روز نمی‌شود.
    try:
        reply_markup = equipment_callbacks.with_admin_edit_button(
            menu_builder.get_device_detail_markup(device, line, hide_definition_row=(action == "definition")),
            device, action, line, update.effective_user.id,
        )
        if action == "definition":
            await context.bot.edit_message_caption(
                chat_id=edit_state["chat_id"], message_id=edit_state["message_id"],
                caption=new_text, reply_markup=reply_markup,
            )
        else:
            await context.bot.edit_message_text(
                chat_id=edit_state["chat_id"], message_id=edit_state["message_id"],
                text=new_text, reply_markup=reply_markup,
            )
    except Exception as e:
        logger.warning(f"Could not refresh original message after equipment edit: {e}")

    return ConversationHandler.END


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("equipment_edit", None)
    await update.message.reply_text("ویرایش لغو شد.")
    return ConversationHandler.END


async def remind_text_needed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفاً متن جدید را ارسال کنید، یا /cancel بزنید.")


async def handle_edit_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """هم‌الگو با admin.handle_search_timeout/handle_broadcast_timeout (بند
    ۰.۴) — TypeHandler چون آخرین updateی که PTB اینجا پاس می‌دهد می‌تواند
    پیام متنی یا callback query باشد."""
    context.user_data.pop("equipment_edit", None)
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ زمان ویرایش تمام شد. برای شروع دوباره روی ✏️ بزنید.",
        )


equipment_edit_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit, pattern=r"^admin_edit_field:")],
    states={
        AWAITING_NEW_TEXT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_text),
            MessageHandler(~filters.COMMAND, remind_text_needed),
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, handle_edit_timeout)],
    },
    fallbacks=[CommandHandler("cancel", cancel_edit)],
    conversation_timeout=_CONVERSATION_TIMEOUT_SECONDS,
    name="equipment_field_edit",
)
