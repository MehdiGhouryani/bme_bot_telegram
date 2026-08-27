# src/bme_bot/db/stt_usage_repository.py
#
# محدودیت روزانه و کول‌داون فیچر «تبدیل ویس به متن». سقف بر مبنای «مجموع
# ثانیه‌ی صدای پردازش‌شده‌ی امروز» است، نه «تعداد درخواست» — چون هزینه‌ی
# واقعی این فیچر (سهمیه‌ی provider ها) بر مبنای audio-second حساب می‌شود،
# نه تعداد فایل. به همین دلیل این فایل برخلاف ai/ocr/quiz/jozve به
# db/usage_limit_helper.py مشترک منتقل نشده — منطقش کاملاً متفاوت است.
#
# ستون request_count همچنان همین نام را دارد ولی معنایش «ثانیه‌ی
# مصرف‌شده‌ی امروز» است، نه تعداد فایل.

import time
from datetime import date
from typing import Tuple

from . import app_connection, feature_limits_repository

_FEATURE_NAME = "stt"


async def check_stt_limit(user_id: int, duration_seconds: int) -> Tuple[bool, str]:
    """سقف روزانه (بر مبنای مجموع ثانیه) و کول‌داون کاربر را بررسی می‌کند.
    duration_seconds مدت *همین* فایلی است که می‌خواهد پردازش شود - قبل از
    پردازش چک می‌شود که اضافه‌شدنش سقف را رد نکند."""
    daily_limit_seconds, cooldown_seconds, _ = await feature_limits_repository.get_limit(_FEATURE_NAME)
    today = date.today().isoformat()
    current_time = int(time.time())

    async with app_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT request_count, last_request_date, last_request_timestamp "
            "FROM stt_usage WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            used_seconds, last_date, last_timestamp = result

            if current_time - last_timestamp < cooldown_seconds:
                remaining_time = cooldown_seconds - (current_time - last_timestamp)
                return False, f"لطفاً {remaining_time} ثانیه دیگر دوباره تلاش کنید."

            if last_date != today:
                await conn.execute(
                    "UPDATE stt_usage SET request_count = 0 WHERE user_id = ?", (user_id,)
                )
                used_seconds = 0

            if used_seconds + duration_seconds > daily_limit_seconds:
                await conn.commit()
                remaining_minutes = max(0, daily_limit_seconds - used_seconds) // 60
                return False, (
                    f"سقف روزانه‌ی {daily_limit_seconds // 60} دقیقه صدا پر شده "
                    f"(فقط حدود {remaining_minutes} دقیقه باقی مانده)."
                )
        else:
            await conn.execute(
                "INSERT INTO stt_usage (user_id, last_request_date, last_request_timestamp) "
                "VALUES (?, ?, ?)",
                (user_id, today, 0),
            )
            if duration_seconds > daily_limit_seconds:
                await conn.commit()
                return False, f"این فایل از سقف روزانه‌ی {daily_limit_seconds // 60} دقیقه بیشتره."

        await conn.commit()

    return True, "OK"


async def record_attempt(user_id: int) -> None:
    """فقط last_request_timestamp را به‌روز می‌کند — کول‌داون حتی روی تلاشی
    که در ادامه با خطای واقعی provider مواجه می‌شود هم باید اعمال شود."""
    current_time = int(time.time())

    async with app_connection.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO stt_usage (user_id, last_request_timestamp)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            last_request_timestamp = ?
            """,
            (user_id, current_time, current_time),
        )
        await conn.commit()


async def increment_stt_usage(user_id: int, duration_seconds: int) -> None:
    """مجموع ثانیه‌ی مصرف‌شده‌ی امروز را با مدت *واقعی* فایل پردازش‌شده
    جمع می‌زند (نه +۱ ثابت مثل قبل)."""
    today = date.today().isoformat()

    async with app_connection.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO stt_usage (user_id, request_count, last_request_date)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            request_count = request_count + ?,
            last_request_date = ?
            """,
            (user_id, duration_seconds, today, duration_seconds, today),
        )
        await conn.commit()
