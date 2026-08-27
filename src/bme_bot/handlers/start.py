# src/bme_bot/handlers/start.py
#
# start() از دو مسیر صدا زده می‌شود: (۱) دستور /start معمولی، (۲) از داخل
# membership.check_membership() بعد از تایید موفق عضویت — که خودش از یک
# callback_query می‌آید. در python-telegram-bot، برای آپدیت‌هایی که فقط
# callback_query دارند (نه پیام مستقل)، فیلد update.message برابر None است؛
# فقط update.callback_query.message / update.effective_message پر می‌شوند.
# اگر اینجا از update.message.reply_text استفاده شود، در مسیر (۲)
# AttributeError می‌دهد (کاربر به‌جای پیام خوش‌آمدگویی، خطای عمومی می‌بیند).
# update.effective_message در هر دو حالت به‌درستی resolve می‌شود، پس همین
# یک تغییر هر دو مسیر را پوشش می‌دهد بدون نیاز به شاخه‌بندی جداگانه برای
# callback_query.

from telegram import Update
from telegram.ext import ContextTypes

from ..db import users_repository
from ..keyboards import reply_keyboards


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """با شروع ربات، اطلاعات کاربر را ذخیره کرده و منوی اصلی را نمایش می‌دهد."""
    user = update.effective_user

    await users_repository.save_user(user.id, user.username, update.effective_chat.id)

    reply_markup = reply_keyboards.main_menu_keyboard(one_time=True)
    await update.effective_message.reply_text(
        "سلام! به ربات دستیار مهندسی پزشکی خوش آمدید.\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=reply_markup,
    )


async def handle_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_markup = reply_keyboards.main_menu_keyboard(one_time=False)
    await update.message.reply_text("لطفا یکی از گزینه‌ها را انتخاب کنید:", reply_markup=reply_markup)
