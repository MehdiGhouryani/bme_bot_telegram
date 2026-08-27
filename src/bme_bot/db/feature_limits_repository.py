# src/bme_bot/db/feature_limits_repository.py
#
# منبع واحد سقف روزانه/کول‌داون هر فیچر، قابل‌ویرایش از پنل ادمین بدون نیاز
# به دیپلوی مجدد. پنج ردیف seed در app_connection.setup_users_database() با
# INSERT OR IGNORE درج می‌شوند — یعنی اگر ادمین قبلاً یک مقدار را از پنل
# عوض کرده باشد، ری‌استارت بات هرگز رویش نمی‌نویسد.
#
# unit فقط برای STT برابر 'seconds' است (بقیه 'count') — همان تمایزی که
# در stt_usage_repository.py توضیح داده شده: سقف STT بر مبنای مجموع مدت
# صدای پردازش‌شده است، نه تعداد فایل.

from typing import Tuple

from . import app_connection

# اگر به هر دلیلی ردیف feature_limits برای یک فیچر نبود (مثلاً یک دیتابیس
# خیلی قدیمی که هنوز migrate نشده)، این‌ها فقط fallback ایمن‌اند - نه منبع
# حقیقت؛ منبع حقیقت همیشه جدول feature_limits است.
_FALLBACK_DEFAULTS = {
    "ai": (5, 60, "count"),
    "ocr": (5, 60, "count"),
    "stt": (300, 60, "seconds"),
    "quiz": (5, 60, "count"),
    "jozve": (1, 120, "count"),
}


async def get_limit(feature_name: str) -> Tuple[int, int, str]:
    """(daily_limit, cooldown_seconds, unit) را برمی‌گرداند."""
    async with app_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT daily_limit, cooldown_seconds, unit FROM feature_limits WHERE feature_name = ?",
            (feature_name,),
        ) as cursor:
            row = await cursor.fetchone()
    if row:
        return row[0], row[1], row[2]
    return _FALLBACK_DEFAULTS.get(feature_name, (5, 60, "count"))


async def set_daily_limit(feature_name: str, new_daily_limit: int) -> None:
    """از پنل ادمین صدا زده می‌شود. اگر ردیف هنوز نبود (edge case)، با
    cooldown/unit پیش‌فرض همان فیچر ساخته می‌شود، نه یک مقدار دلبخواه."""
    _, fallback_cooldown, fallback_unit = _FALLBACK_DEFAULTS.get(feature_name, (5, 60, "count"))
    async with app_connection.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO feature_limits (feature_name, daily_limit, cooldown_seconds, unit)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(feature_name) DO UPDATE SET daily_limit = ?
            """,
            (feature_name, new_daily_limit, fallback_cooldown, fallback_unit, new_daily_limit),
        )
        await conn.commit()


async def get_all_limits() -> list:
    """برای نمایش کامل تو پنل ادمین. هر آیتم:
    {feature_name, daily_limit, cooldown_seconds, unit}."""
    async with app_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT feature_name, daily_limit, cooldown_seconds, unit "
            "FROM feature_limits ORDER BY feature_name"
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {"feature_name": r[0], "daily_limit": r[1], "cooldown_seconds": r[2], "unit": r[3]}
        for r in rows
    ]
