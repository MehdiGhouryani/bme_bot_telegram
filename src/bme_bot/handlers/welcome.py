# src/bme_bot/handlers/welcome.py
#
# خوشامدگویی خودکار اعضای جدید گروه — قابل فعال/غیرفعال و قابل‌ویرایش از
# پنل ادمین (بخش «⚙️ تنظیمات بات»)، بدون نیاز به دیپلوی مجدد برای تغییر
# متن یا خاموش/روشن‌کردنش. یک فایل جدا (نه داخل admin.py)، دقیقاً به همون
# دلیلی که equipment_admin_edit.py جدا نگه داشته شده: این فیچر مفهوماً به
# دامنه‌ی خوشامدگویی/گروه نزدیک‌تره تا مدیریت کاربر/Broadcast/سلامت سیستم.
#
# ترigger: filters.StatusUpdate.NEW_CHAT_MEMBERS (سرویس‌پیام کلاسیک «فلان
# کاربر عضو شد»)، نه ChatMemberHandler. دلیل: Application.run_polling() فعلی
# (app.py) هیچ allowed_updates صریحی نمی‌ده، و طبق رفتار مستندِ خودِ Bot API
# (نه چیزی خاص این پروژه)، بدون allowed_updates صریح، آپدیت‌های نوع
# chat_member اصلاً از تلگرام دریافت نمی‌شن (برخلاف پیام‌های معمولی که
# همیشه می‌رسن، چون بات همین الان هم بدون مشکل بهشون واکنش نشون می‌ده) —
# پس ChatMemberHandler بدون یک تغییر جداگانه در بوت‌استرپ run_polling عملاً
# هیچ‌وقت fire نمی‌شد. این مسیر ساده‌تر، بدون دست‌زدن به بوت‌استرپ اصلی
# Application، همون کاری رو می‌کنه که اکثر گروه‌ها لازم دارن؛ تنها قیمتش
# اینه که یک سناریوی نادر (گروه‌هایی که تنظیم «نمایش پیام عضویت» رو صریح
# خاموش کرده باشن) رو پوشش نمی‌ده — اگه در عمل لازم شد، ارتقا به
# ChatMemberHandler + تغییر run_polling یک قدم مجزا و مشخصه، نه بخشی از
# این تغییر.
#
# *** نکته‌ی حیاتی برای ثبت در app.py ***
# welcome_edit_conversation باید در app.py *قبل* از CallbackQueryHandler
# (callback_handler) عمومی ثبت شود — دقیقاً همون الزامی که admin.py و
# equipment_admin_edit.py برای ConversationHandlerهای خودشون مستند کردن؛
# callback_handler عمومی الگوی "admin_settings_welcome_edit_start" رو به‌عنوان
# یه کلیک ناشناخته نادیده می‌گیره (نه کرش)، ولی دکمه‌ی ✏️ عملاً بی‌اثر می‌مونه.

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

from ..db import settings_repository
from ..utils.admin import is_admin
from ..utils.entities_to_markdown import FLAVOR_RICH, entities_to_markdown
from ..utils.rich_message import send_rich_message

logger = logging.getLogger(__name__)

WELCOME_ENABLED_KEY = "welcome_enabled"
WELCOME_TEXT_KEY = "welcome_text"
# پیش‌فرض *fallback* است، نه منبع حقیقت — دقیقاً همون تمایزی که
# feature_limits_repository._FALLBACK_DEFAULTS مستند می‌کنه: بعد از اولین
# ذخیره از پنل، این مقدار دیگه هیچ‌وقت خونده نمی‌شه.
DEFAULT_WELCOME_TEXT = (
    "🎉 به گروه دانشجویان مهندسی پزشکی خوش اومدی {name}!\n"
    "برای استفاده از امکانات بات (پرسش‌وپاسخ هوشمند، تبدیل عکس/ویس به متن، "
    "کوییز و ...) کافیه وارد چت خصوصی با بات بشی و /start رو بزنی."
)
_SAMPLE_NAME_FOR_PREVIEW = "علی"

AWAITING_TEXT = "welcome_edit_awaiting_text"
AWAITING_CONFIRMATION = "welcome_edit_awaiting_confirmation"
# بدون JobQueue فعال (python-telegram-bot[job-queue] extra)، این پارامتر
# بی‌اثر می‌ماند — عیناً همون نکته‌ی مستندشده در admin.py/equipment_admin_edit.py.
_CONVERSATION_TIMEOUT_SECONDS = 300


async def is_welcome_enabled() -> bool:
    return await settings_repository.get_bool_setting(WELCOME_ENABLED_KEY, default=True)


async def get_welcome_text() -> str:
    return await settings_repository.get_setting(WELCOME_TEXT_KEY, default=DEFAULT_WELCOME_TEXT)


def _render(template: str, name: str) -> str:
    return template.replace("{name}", name)


# کاراکترهای معنادار در Rich Markdown که اگه escape نشن، اسم کاربر می‌تونه
# سینتکس مارک‌داون رو بشکنه یا (مهم‌تر) یه لینک قلابی بسازه که انگار از
# طرف خودِ پیام رسمی بات در گروهه — یه وکتور فیشینگ واقعی، نه صرفاً زیبایی.
# اسم تلگرام کاملاً دست خودِ کاربره (مثلاً می‌تونه بذاره
# "[کلیک کنید](https://evil.com)")، پس در handle_new_chat_members، برخلاف
# _SAMPLE_NAME_FOR_PREVIEW (که یه رشته‌ی ثابت و بی‌خطره)، باید قبل از
# _render از این عبور کنه.
_MARKDOWN_SPECIAL_CHARS = "[]()*_`"


def _escape_untrusted_name(name: str) -> str:
    # ترتیب حیاتیه: اول خودِ بک‌اسلش باید escape بشه، بعد بقیه‌ی کاراکترها —
    # وگرنه اسمی که از قبل یه بک‌اسلش داره (مثلاً "\[لینک](...)") می‌تونه
    # escape خودمون رو خنثی کنه: اگه اول "[" رو به "\[" تبدیل کنیم، بک‌اسلش
    # قبلیِ کاربر کنارش می‌شینه و با هم "\\[" می‌شن — یعنی «بک‌اسلشِ
    # escape‌شده» + یه "[" کاملاً *بی‌escape*، دقیقاً همون سینتکس لینکی که
    # می‌خواستیم خنثی کنیم. با escape کردن بک‌اسلش اول، هر بک‌اسلشِ از قبل
    # موجود در اسم خودش بی‌خطر می‌شه و دیگه نمی‌تونه با escape بعدی ترکیب بشه.
    name = name.replace("\\", "\\\\")
    for ch in _MARKDOWN_SPECIAL_CHARS:
        name = name.replace(ch, "\\" + ch)
    return name


# ============================== ترigger در گروه ==============================

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_welcome_enabled():
        return

    template = await get_welcome_text()
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue  # خودِ بات هم یه بار «عضو جدید» گروهه (وقتی اولین‌بار اضافه می‌شه) — به خودش خوشامد نمی‌گیم.
        text = _render(template, _escape_untrusted_name(member.first_name or "دوست عزیز"))
        ok = await send_rich_message(context.bot, update.effective_chat.id, text)
        if not ok:
            # fallback همیشگی این پروژه برای Rich Message: پیام معمولی، بدون
            # فرمت غنی، ولی حتماً می‌رسه — رجوع به الگوی مشابه در ai_assistant.py.
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


# ============================== پنل ادمین ==============================

def render_settings_menu(enabled: bool) -> tuple:
    """(text, InlineKeyboardMarkup) برای زیرمنوی «⚙️ تنظیمات بات» —
    admin.handle_admin_menu_callback این رو برای admin_menu:settings صدا
    می‌زنه، عیناً همون الگوی _limits_submenu_markup در admin.py."""
    status = "✅ فعال" if enabled else "❌ غیرفعال"
    text = f"⚙️ تنظیمات بات:\n\n🎉 خوشامدگویی اعضای جدید گروه: {status}"
    toggle_label = "❌ غیرفعال کردن خوشامدگویی" if enabled else "✅ فعال کردن خوشامدگویی"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_label, callback_data="admin_settings_welcome_toggle")],
        [InlineKeyboardButton("✏️ ویرایش متن خوشامدگویی", callback_data="admin_settings_welcome_edit_start")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu:main")],
    ])
    return text, markup


async def handle_settings_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """از handle_admin_menu_callback عمومی (admin.py) صدا زده می‌شه —
    ConversationHandler جدا لازم نداره چون فقط یه toggle ساده‌ست، دقیقاً
    مثل admin_menu:health_test و بقیه‌ی زیرمنوهای بدون حالت."""
    query = update.callback_query
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer("⛔ این بخش فقط برای ادمین‌هاست.", show_alert=True)
        return
    await query.answer()
    new_value = not await is_welcome_enabled()
    await settings_repository.set_bool_setting(WELCOME_ENABLED_KEY, new_value)
    text, markup = render_settings_menu(new_value)
    await query.edit_message_text(text, reply_markup=markup)


async def start_welcome_text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer("⛔ این بخش فقط برای ادمین‌هاست.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    current = await get_welcome_text()
    await query.edit_message_text(
        "متن جدید خوشامدگویی رو بفرست.\n"
        "می‌تونی از {name} توی متن استفاده کنی — موقع ارسال، خودکار با اسم عضو جدید جایگزین می‌شه.\n\n"
        f"متن فعلی:\n{current}\n\nبرای لغو، /cancel را بفرستید."
    )
    return AWAITING_TEXT


async def receive_welcome_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دقیقاً همون الگوی equipment_admin_edit.receive_new_text: بازسازی
    فرمت‌دهی زنده‌ی تلگرام از entities (نه پارس متن خام)، پیش‌نمایش واقعی
    از طریق خودِ sendRichMessage برای گرفتن BadRequest واقعی *قبل* از
    ذخیره (نه بعد از این‌که برای اولین عضو جدید خراب از آب دراومد)، و
    ذخیره فقط بعد از تایید صریح."""
    new_text = entities_to_markdown(update.message.text, update.message.entities, flavor=FLAVOR_RICH)
    preview = _render(new_text, _SAMPLE_NAME_FOR_PREVIEW)
    confirm_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تایید و جایگزینی", callback_data="admin_settings_welcome_confirm")],
        [InlineKeyboardButton("❌ لغو", callback_data="admin_settings_welcome_cancel")],
    ])

    try:
        # مستقیم روی do_api_request صدا می‌زنیم (نه از طریق
        # rich_message.send_rich_message که هر خطایی رو یکسان به False
        # تبدیل می‌کنه) چون فقط می‌خوایم «فرمت نامعتبره» (BadRequest واقعی)
        # رو از خطاهای گذرای دیگه (شبکه و غیره) جدا کنیم — عیناً همون
        # استدلال کامنت‌شده در equipment_admin_edit.receive_new_text.
        await context.bot.do_api_request(
            "sendRichMessage",
            {
                "chat_id": update.effective_chat.id,
                "rich_message": {
                    "markdown": f"📝 پیش‌نمایش (با اسم نمونه‌ی «{_SAMPLE_NAME_FOR_PREVIEW}»):\n\n{preview}",
                },
            },
        )
    except BadRequest as e:
        await update.message.reply_text(
            "⚠️ این متن فرمت Rich Markdown معتبری نداره (مثلاً یه `**`، `*` یا `##` بدون "
            "جفت/جای درست) — دقیقاً همین چیزی بود که می‌تونست بعداً پیام خوشامدگویی رو برای "
            f"اولین عضو جدید خراب کنه. لطفاً تصحیحش کنید و دوباره بفرستید، یا /cancel برای انصراف.\n\nجزئیات فنی: {e}"
        )
        return AWAITING_TEXT

    await update.message.reply_text("برای ذخیره‌ی همین متن تایید کنید:", reply_markup=confirm_markup)
    context.user_data["pending_welcome_text"] = new_text
    return AWAITING_CONFIRMATION


async def confirm_welcome_text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    new_text = context.user_data.pop("pending_welcome_text", None)
    if new_text is None:
        # نباید عملاً پیش بیاد (state فقط با receive_welcome_text ست می‌شه)،
        # ولی یک محافظ دفاعی ارزان است — بهتر از KeyError/رفتار نامشخص.
        await query.edit_message_text("خطای داخلی — لطفاً دوباره از روی ✏️ شروع کنید.")
        return ConversationHandler.END
    await settings_repository.set_setting(WELCOME_TEXT_KEY, new_text)
    await query.edit_message_text("✅ متن خوشامدگویی ذخیره شد.")
    return ConversationHandler.END


async def cancel_welcome_text_edit_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("pending_welcome_text", None)
    await query.edit_message_text("ویرایش لغو شد.")
    return ConversationHandler.END


async def cancel_welcome_text_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("pending_welcome_text", None)
    await update.message.reply_text("ویرایش متن خوشامدگویی لغو شد.")
    return ConversationHandler.END


async def handle_welcome_edit_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_welcome_text", None)
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ زمان ویرایش متن خوشامدگویی تمام شد و لغو شد. برای شروع دوباره /admin را بزنید.",
        )


welcome_edit_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_welcome_text_edit, pattern=r"^admin_settings_welcome_edit_start$"),
    ],
    states={
        AWAITING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_welcome_text)],
        AWAITING_CONFIRMATION: [
            CallbackQueryHandler(confirm_welcome_text_edit, pattern=r"^admin_settings_welcome_confirm$"),
            CallbackQueryHandler(
                cancel_welcome_text_edit_confirmation, pattern=r"^admin_settings_welcome_cancel$",
            ),
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, handle_welcome_edit_timeout)],
    },
    fallbacks=[CommandHandler("cancel", cancel_welcome_text_edit)],
    conversation_timeout=_CONVERSATION_TIMEOUT_SECONDS,
    name="admin_welcome_edit",
)
