# src/bme_bot/utils/admin.py
#
# نسخه‌ی یکپارچه‌ی is_admin — تنها جایی که چک عضویت در ADMIN_CHAT_ID انجام
# می‌شود، تا این منطق در فایل‌های مختلف تکرار/ناهماهنگ نشود.
#
# notify_admins: بدون محافظت per-admin (زیر را ببینید)، یک ادمین بلاک‌کرده
# می‌تواند کل تابع فراخواننده را با یک Exception متوقف کند — نمونه‌اش
# handlers/suggestion.py.

import logging

from telegram.ext import ContextTypes

from .. import config

logger = logging.getLogger(__name__)


def is_admin(user_id) -> bool:
    return str(user_id) in config.ADMIN_CHAT_ID


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode=None) -> None:
    """پیامی را به همه‌ی ادمین‌های موجود در ADMIN_CHAT_ID می‌فرستد.

    ارسال به هر ادمین جدا از بقیه محافظت می‌شود: اگر یکی شکست بخورد (مثلاً
    بلاک کرده باشد)، بقیه همچنان پیام را دریافت می‌کنند و فراخواننده هم هرگز
    به‌خاطر این شکست متوقف نمی‌شود.
    """
    if not isinstance(config.ADMIN_CHAT_ID, (list, tuple)) or not config.ADMIN_CHAT_ID:
        logger.warning("ADMIN_CHAT_ID خالی یا نامعتبر است — پیام به هیچ ادمینی ارسال نشد.")
        return

    for admin_id in config.ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin_id}: {e}")
