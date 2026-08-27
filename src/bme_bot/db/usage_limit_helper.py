# src/bme_bot/db/usage_limit_helper.py
#
# منطق مشترک محدودیت شمارشی (نه بر مبنای مدت) بین AI/OCR/کوییز/جزوه — این
# چهارتا ساختار SQL کاملاً یکسانی دارند (فقط اسم جدول فرق می‌کند)؛ با
# خواندن سقف از feature_limits (به‌جای ثابت پایتون)، این تکرار بیشتر هم
# می‌شد. استخراج این منطق باعث نمی‌شود فیچرها جدول/فایل مستقل خود را از
# دست بدهند — هرکدام همچنان جدول و فایل خودشان را دارند
# (db/ai_usage_repository.py و ...)، فقط دیگر پیاده‌سازی SQL را کپی
# نمی‌کنند؛ امضای توابع عمومی هرکدام هم دست‌نخورده مانده، پس هیچ handler ای
# نیازی به تغییر فراخوانی ندارد.
#
# STT اینجا نیست: چون بر مبنای «مجموع ثانیه»‌ست نه شمارش، منطقش کاملاً
# متفاوت است — جدا و دستی در stt_usage_repository.py.
#
# نکته‌ی امنیتی: table_name هرگز از ورودی کاربر نمی‌آید (همیشه یک رشته‌ی
# هاردکد از خودِ چهار فایل repository است)، ولی چون در query با f-string
# ساخته می‌شود (SQLite پارامتر جای‌گذاری‌شده برای نام جدول/ستون پشتیبانی
# نمی‌کند)، یک allow-list صریح هم اینجا اضافه شده — همون الگوی امنیتی که در
# equipment_repository.py برای نام ستون/جدول اعتبارسنجی‌نشده لازم شد.

import time
from datetime import date
from typing import Tuple

from . import app_connection, feature_limits_repository

_ALLOWED_TABLES = {"ai_usage", "ocr_usage", "quiz_usage", "jozve_usage"}


def _validate_table(table_name: str) -> None:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"جدول محدودیت غیرمجاز: {table_name!r}")


async def check_limit(table_name: str, feature_name: str, user_id: int) -> Tuple[bool, str]:
    _validate_table(table_name)
    daily_limit, cooldown_seconds, _ = await feature_limits_repository.get_limit(feature_name)
    today = date.today().isoformat()
    current_time = int(time.time())

    async with app_connection.get_connection() as conn:
        async with conn.execute(
            f"SELECT request_count, last_request_date, last_request_timestamp "
            f"FROM {table_name} WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            count, last_date, last_timestamp = result

            if current_time - last_timestamp < cooldown_seconds:
                remaining_time = cooldown_seconds - (current_time - last_timestamp)
                return False, f"لطفاً {remaining_time} ثانیه دیگر دوباره تلاش کنید."

            if last_date != today:
                await conn.execute(
                    f"UPDATE {table_name} SET request_count = 0 WHERE user_id = ?", (user_id,)
                )
                count = 0

            if count >= daily_limit:
                await conn.commit()
                return False, f"شما از تمام {daily_limit} استفاده‌ی روزانه‌ی خود استفاده کرده‌اید."
        else:
            await conn.execute(
                f"INSERT INTO {table_name} (user_id, last_request_date, last_request_timestamp) "
                f"VALUES (?, ?, ?)",
                (user_id, today, 0),
            )

        await conn.commit()

    return True, "OK"


async def record_attempt(table_name: str, user_id: int) -> None:
    _validate_table(table_name)
    current_time = int(time.time())
    async with app_connection.get_connection() as conn:
        await conn.execute(
            f"""
            INSERT INTO {table_name} (user_id, last_request_timestamp)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            last_request_timestamp = ?
            """,
            (user_id, current_time, current_time),
        )
        await conn.commit()


async def increment_usage(table_name: str, user_id: int) -> None:
    _validate_table(table_name)
    today = date.today().isoformat()
    async with app_connection.get_connection() as conn:
        await conn.execute(
            f"""
            INSERT INTO {table_name} (user_id, request_count, last_request_date)
            VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            request_count = request_count + 1,
            last_request_date = ?
            """,
            (user_id, today, today),
        )
        await conn.commit()
