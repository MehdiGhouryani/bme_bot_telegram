# src/bme_bot/db/error_log_repository.py
#
# لاگ خطای فشرده و هوشمند: یک ردیف به‌ازای هر اثرانگشتِ *یکتا* (رجوع به
# utils/error_fingerprint.py)، نه هر رخداد — یعنی اندازه‌ی این جدول عملاً
# محدود به «تعداد باگ‌های واقعاً متفاوت»، نه «تعداد دفعاتی که رخ دادن».
# حتی اگه یه باگ ۱۰۰۰۰ بار تکرار بشه (دقیقاً همون سناریوی حلقه‌ی کرش
# equipment_admin_edit در تاریخچه‌ی پروژه)، همچنان فقط یک ردیفه: count
# بالا می‌ره، last_seen به‌روز می‌شه، ولی sample_traceback از رخداد *اول*
# دست‌نخورده می‌مونه — چون یه نمونه‌ی کامل کافیه، نمونه‌ی صدم چیز جدیدی
# اضافه نمی‌کنه.
#
# جدا از feature_usage عمداً: اون جدول برای «کدوم provider چقدر
# موفق/ناموفق بوده» (سیگنال آماری تجمعی) طراحی شده، این‌جا برای «دقیقاً
# چه باگ‌های *غیرمنتظره‌ای* در کد خودمون رخ دادن» (سیگنال دیباگ سطح
# کد) — دو دغدغه‌ی متفاوت که قاطی‌کردنشون هر دو رو کدر می‌کرد.
#
# محدودیت روی عمر/تعداد ردیف عمداً گذاشته نشده — چون برخلاف لاگ‌های
# usage/audit که روزانه رشد می‌کنن، رشد این جدول محدود به کشف باگ *جدید*
# است، نه تکرار باگ قدیمی؛ در یه پروژه‌ی فعال و تست‌شده، این عملاً خیلی
# کند رشد می‌کنه. اگه یه روز واقعاً لازم شد، حذف/آرشیو دستی از پنل ادمین
# (نه یه سیاست خودکار سرِ حدس) قدم بعدیه.

from datetime import datetime, timezone

from . import app_connection


async def record_error(fingerprint: str, exception_type: str, location: str, traceback_text: str) -> int:
    """ثبت یا به‌روزرسانی یک رخداد. خروجی: تعداد کل رخدادهای این
    اثرانگشت *بعد* از این ثبت (۱ یعنی این اولین بار بود — فراخواننده
    معمولاً از همین برای تصمیم «traceback کامل بفرستم یا فقط بگم دوباره
    تکرار شد» استفاده می‌کنه).

    timespec="seconds" عمداً استفاده *نشده* — در یک خرابی آبشاری، چند
    باگ *متفاوت* می‌تونن کاملاً داخل یک ثانیه رخ بدن؛ دقت میکروثانیه‌ای
    (ایزوفرمت کامل پیش‌فرض) این‌که get_recent_errors واقعاً به ترتیب
    آخرین رخداد مرتب بشه رو (نه به ترتیب رخداد تصادفیِ SQLite روی مقادیر
    یکسان) تضمین می‌کنه."""
    now = datetime.now(timezone.utc).isoformat()
    async with app_connection.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO error_log (fingerprint, exception_type, location, count, first_seen, last_seen, sample_traceback)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET count = count + 1, last_seen = ?
            """,
            (fingerprint, exception_type, location, now, now, traceback_text, now),
        )
        await conn.commit()
        async with conn.execute(
            "SELECT count FROM error_log WHERE fingerprint = ?", (fingerprint,),
        ) as cursor:
            row = await cursor.fetchone()
    return row[0] if row else 1


async def get_recent_errors(limit: int = 20) -> list[dict]:
    """برای نمایش «🪲 خطاهای اخیر» در پنل ادمین — تازه‌ترین‌ها اول."""
    async with app_connection.get_connection() as conn:
        async with conn.execute(
            """
            SELECT fingerprint, exception_type, location, count, first_seen, last_seen, sample_traceback
            FROM error_log ORDER BY last_seen DESC LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {
            "fingerprint": r[0], "exception_type": r[1], "location": r[2],
            "count": r[3], "first_seen": r[4], "last_seen": r[5], "sample_traceback": r[6],
        }
        for r in rows
    ]
