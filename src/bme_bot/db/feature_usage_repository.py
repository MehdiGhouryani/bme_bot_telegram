# src/bme_bot/db/feature_usage_repository.py
#
# ثبت و تجمیع تعاملات کاربران با بخش‌های مختلف ربات — منبع خام بخش «آمار»
# پنل ادمین. عمداً فقط نام فیچر + جزئیات کوتاه اختیاری (مثلاً کدام لایه‌ی
# AI/OCR پاسخ داد) ذخیره می‌شود — به دلایل حریم خصوصی، هرگز متن کامل
# سوال/نتیجه‌ی OCR کاربر اینجا ذخیره نمی‌شود.

from datetime import datetime, timezone

from . import app_connection


def _now_iso() -> str:
    """زمان فعلی UTC، هم‌فرمت با خروجی SQLite datetime() — رفع باگ مقایسه‌ی
    فرمت که در db/users_repository.py._now_iso به‌طور کامل مستند شده؛ همان
    دلیل اینجا هم صدق می‌کند چون get_feature_counts/get_detail_breakdown
    عیناً همان الگوی `timestamp >= datetime('now', ?)` را دارند."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def log_usage(user_id: int, feature: str, detail: str = None):
    """یک تعامل را ثبت می‌کند. عمداً هیچ استثنایی به بیرون raise نمی‌کند — این
    فقط آمار است، نباید یک شکست اینجا جریان اصلی هندلر (مثلاً پاسخ AI به
    کاربر) را بترکاند. فراخواننده باید این را «fire and forget» صدا بزند."""
    try:
        async with app_connection.get_connection() as conn:
            await conn.execute(
                "INSERT INTO feature_usage (user_id, feature, detail, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, feature, detail, _now_iso()),
            )
            await conn.commit()
    except Exception:
        # طبق کامنت بالا: خطای ثبت آمار نباید هیچ‌وقت کاربر واقعی را متاثر کند.
        # لاگ اینجا لازم نیست چون RotatingFileHandler خودش هر Exception
        # مدیریت‌نشده‌ی سطح‌بالاتر را می‌گیرد؛ این try/except صرفاً از انتشار
        # جلوگیری می‌کند.
        pass


async def get_feature_counts(days: int = None) -> dict:
    """تعداد تعامل هر فیچر را برمی‌گرداند (برای «پربازدیدترین بخش‌ها»).
    days=None یعنی کل تاریخچه؛ در غیر این صورت فقط N روز اخیر."""
    async with app_connection.get_connection() as conn:
        if days is None:
            sql = "SELECT feature, COUNT(*) FROM feature_usage GROUP BY feature ORDER BY COUNT(*) DESC"
            params = ()
        else:
            sql = (
                "SELECT feature, COUNT(*) FROM feature_usage "
                "WHERE timestamp >= datetime('now', ?) GROUP BY feature ORDER BY COUNT(*) DESC"
            )
            params = (f"-{days} days",)

        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()

    return {feature: count for feature, count in rows}


async def get_detail_breakdown(feature: str, days: int = None) -> dict:
    """تفکیک مقدار detail برای یک فیچر خاص (مثلاً کدام لایه‌ی AI/OCR چند بار
    پاسخ داده) — برای بخش «سلامت سیستم» پنل ادمین."""
    async with app_connection.get_connection() as conn:
        if days is None:
            sql = (
                "SELECT detail, COUNT(*) FROM feature_usage "
                "WHERE feature = ? AND detail IS NOT NULL GROUP BY detail ORDER BY COUNT(*) DESC"
            )
            params = (feature,)
        else:
            sql = (
                "SELECT detail, COUNT(*) FROM feature_usage "
                "WHERE feature = ? AND detail IS NOT NULL AND timestamp >= datetime('now', ?) "
                "GROUP BY detail ORDER BY COUNT(*) DESC"
            )
            params = (feature, f"-{days} days")

        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()

    return {detail: count for detail, count in rows}
