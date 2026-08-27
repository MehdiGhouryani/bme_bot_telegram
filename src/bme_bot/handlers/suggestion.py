# src/bme_bot/handlers/suggestion.py
#
# حلقه‌ی ارسال به ادمین‌ها اینجا خودش try/except ندارد — اگر ارسال به یک
# ادمین شکست بخورد (مثلاً بلاک کرده باشد)، از notify_admins مشترک
# (utils/admin.py) استفاده می‌شود که این محافظت را خودش دارد؛ بدون آن، یک
# ادمین بلاک‌کرده می‌توانست کل تابع را متوقف کند و کاربر حتی پیام «ممنون از
# پیشنهادتون» را هم نبیند.

from telegram import Update
from telegram.ext import ContextTypes

from ..utils.admin import notify_admins


async def handle_suggestion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['awaiting_request'] = True
    await update.message.reply_text(
        'سلام مهندس🙂\n خوشحال می‌شیم پیشنهادات و ایده‌های خودت رو درباره ربات با ما به اشتراک بذارید.\n\n'
        'لطفاً پیشنهادات خودتون رو همین‌جا بنویسید و ارسال کنید :'
    )


async def handle_suggestion_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user = update.message.from_user
    username = f"@{user.username}" if user.username else "—"
    admin_message = (
        f"پیشنهاد جدید از سمت {user.full_name} دریافت شد!\n"
        f"نام کاربری: {username}\n"
        f"آیدی کاربر: {user.id}\n"
        f"متن پیشنهاد: {user_message}"
    )
    await notify_admins(context, admin_message)
    await update.message.reply_text('ممنون از پیشنهادتون! ما اون رو بررسی خواهیم کرد.')
    context.user_data['awaiting_request'] = False
