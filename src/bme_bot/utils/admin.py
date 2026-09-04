# src/bme_bot/utils/admin.py
#
# نسخه‌ی یکپارچه‌ی is_admin — تنها جایی که چک عضویت در ADMIN_CHAT_ID انجام
# می‌شود، تا این منطق در فایل‌های مختلف تکرار/ناهماهنگ نشود.
#
# ادمین‌های دینامیک (اضافه‌شده از داخل بات توسط ادمین اصلی، نه از .env):
# is_admin() در ~۲۰ جای مختلف کدبیس به‌صورت sync صدا زده می‌شود
# (equipment_callbacks، quiz، ocr، stt، ai_assistant، admin.py خودش،
# equipment_admin_edit، maintenance_admin_edit، ...). async کردنش یعنی
# لمس همه‌ی اون ~۲۰ call site، با ریسک واقعی جا افتادن یکی‌شون. به‌جاش یک
# کش حافظه‌ای ساده (`_dynamic_admin_ids`) نگه می‌داریم که فقط موقع استارت
# بات (load_dynamic_admins، از app._post_init) و موقع افزودن/حذف ادمین
# (handlers/admin.py) به‌روز می‌شود — is_admin() همچنان sync و ارزان
# می‌ماند، درست مثل چک استاتیک config.ADMIN_CHAT_ID.
#
# notify_admins: بدون محافظت per-admin (زیر را ببینید)، یک ادمین بلاک‌کرده
# می‌تواند کل تابع فراخواننده را با یک Exception متوقف کند — نمونه‌اش
# handlers/suggestion.py.

import logging

from telegram.ext import ContextTypes

from .. import config
from ..db import admins_repository

logger = logging.getLogger(__name__)

_dynamic_admin_ids: set[str] = set()


async def load_dynamic_admins() -> None:
    """کش حافظه‌ای ادمین‌های دینامیک را از دیتابیس پر می‌کند — یک‌بار موقع
    استارت بات (app._post_init)، بعد از setup_users_database. تا قبل از این
    فراخوانی، is_admin() فقط config.ADMIN_CHAT_ID استاتیک را می‌بیند."""
    global _dynamic_admin_ids
    try:
        rows = await admins_repository.list_admins()
        _dynamic_admin_ids = {str(row["user_id"]) for row in rows}
    except Exception as e:
        logger.error("failed to load dynamic admins from db: %s", e)


def is_admin(user_id) -> bool:
    return str(user_id) in config.ADMIN_CHAT_ID or str(user_id) in _dynamic_admin_ids


def is_main_admin(user_id) -> bool:
    """فقط ادمین اصلی (config.MAIN_ADMIN_CHAT_ID) — تنها کسی که مجاز است
    ادمین اضافه/حذف کند. یک ادمین دینامیک یا حتی یک ردیف دیگر از فهرست
    استاتیک ADMIN_CHAT_ID، is_main_admin نیست."""
    return config.MAIN_ADMIN_CHAT_ID is not None and str(user_id) == str(config.MAIN_ADMIN_CHAT_ID)


async def add_dynamic_admin(user_id: int, added_by: int) -> None:
    await admins_repository.add_admin(user_id, added_by)
    _dynamic_admin_ids.add(str(user_id))


async def remove_dynamic_admin(user_id: int) -> bool:
    removed = await admins_repository.remove_admin(user_id)
    _dynamic_admin_ids.discard(str(user_id))
    return removed


async def notify_admins(context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode=None) -> None:
    """پیامی را به همه‌ی ادمین‌ها می‌فرستد — هم فهرست استاتیک ADMIN_CHAT_ID
    (از .env)، هم ادمین‌های دینامیک (اضافه‌شده از پنل). یک user_id که به هر
    دو شکل باشد (نباید عملاً پیش بیاید) دوبار پیام نمی‌گیرد.

    ارسال به هر ادمین جدا از بقیه محافظت می‌شود: اگر یکی شکست بخورد (مثلاً
    بلاک کرده باشد)، بقیه همچنان پیام را دریافت می‌کنند و فراخواننده هم هرگز
    به‌خاطر این شکست متوقف نمی‌شود.
    """
    static_ids = config.ADMIN_CHAT_ID if isinstance(config.ADMIN_CHAT_ID, (list, tuple)) else []
    all_ids = dict.fromkeys([*static_ids, *_dynamic_admin_ids])  # ترتیب حفظ می‌شود، تکراری حذف

    if not all_ids:
        logger.warning("هیچ ادمینی (نه در ADMIN_CHAT_ID، نه دینامیک) پیدا نشد — پیام ارسال نشد.")
        return

    for admin_id in all_ids:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, parse_mode=parse_mode)
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin_id}: {e}")
