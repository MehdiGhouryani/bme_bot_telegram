# src/bme_bot/db/settings_repository.py
#
# منبع واحد و عمومی (key→value) برای تنظیمات ساده‌ی قابل‌تغییر از پنل ادمین
# بدون نیاز به دیپلوی مجدد — شبیه feature_limits_repository.py ولی برای
# تنظیماتی که شکل ثابت «سقف روزانه/کول‌داون» ندارن. اولین مصرف‌کننده:
# handlers/welcome.py (فعال/غیرفعال و متن خوشامدگویی).
#
# برخلاف equipment_repository.py (که به‌خاطر عدم اطمینان از UNIQUE constraint
# روی جدول واقعی production از SELECT-then-branch استفاده می‌کنه)، این‌جا
# ON CONFLICT کاملاً امنه: جدول bot_settings توسط خودِ این پروژه از صفر
# ساخته می‌شه (نه یک جدول قدیمی/خارجی با schema نامطمئن) و PRIMARY KEY واقعی
# روی key در app_connection.setup_users_database() تضمین‌شده است.

from . import app_connection

_TRUE_VALUES = {"1", "true"}


async def get_setting(key: str, default: str) -> str:
    async with app_connection.get_connection() as conn:
        async with conn.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with app_connection.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?
            """,
            (key, value, value),
        )
        await conn.commit()


async def get_bool_setting(key: str, default: bool) -> bool:
    """مقدار به‌شکل رشته‌ی "1"/"0" ذخیره می‌شه (نه عدد صحیح SQLite)، چون
    ستون value برای همه‌ی تنظیمات (متنی یا بولی) یکسان TEXT است."""
    raw = await get_setting(key, "1" if default else "0")
    return raw.strip().lower() in _TRUE_VALUES


async def set_bool_setting(key: str, value: bool) -> None:
    await set_setting(key, "1" if value else "0")
