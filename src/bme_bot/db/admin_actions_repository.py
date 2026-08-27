# src/bme_bot/db/admin_actions_repository.py
#
# لاگ اقدامات حساس ادمین (بن/آنبن کاربر، ارسال Broadcast). این صرفاً
# «ردیابی» نیست — محافظی در برابر خطای انسانی است (مثلاً یک Broadcast
# اشتباهی)، درست مثل حریم خصوصی که برای feature_usage رعایت شده: اینجا هم
# متن کامل کپشن Broadcast ذخیره نمی‌شود، فقط خلاصه‌ای که برای بازبینی کافی
# باشد. برای Broadcast این خلاصه دقیقاً «تعداد موفق/ناموفق از کل» است (نه
# طول کپشن یا چیز دیگری از محتوای خودِ پیام) — نگاه کنید به فراخوانی
# log_action در admin._broadcast_worker.

from datetime import datetime, timezone

from . import app_connection


def _now_iso() -> str:
    """زمان فعلی UTC، هم‌فرمت با خروجی SQLite datetime() — رفع باگ مقایسه‌ی
    فرمت که در db/users_repository.py._now_iso مستند شده. get_recent_actions
    فعلاً بر اساس id مرتب می‌شود نه timestamp، پس این فایل عملاً به این باگ
    آسیب نمی‌دید؛ فقط برای یکدستی و پیشگیری از تکرار همین تله در آینده
    (اگر get_recent_actions روزی یک فیلتر بازه‌ای بگیرد) اصلاح شد."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def log_action(admin_id: int, action: str, target: str = None):
    """یک اقدام ادمین را ثبت می‌کند. برخلاف feature_usage.log_usage، این تابع
    عمداً خطای احتمالی را قورت نمی‌دهد و به فراخواننده اجازه می‌دهد تصمیم
    بگیرد (برخلاف آمار عمومی، ثبت‌نشدن یک اقدام حساس باید قابل‌توجه باشد)."""
    async with app_connection.get_connection() as conn:
        await conn.execute(
            "INSERT INTO admin_actions (admin_id, action, target, timestamp) VALUES (?, ?, ?, ?)",
            (admin_id, action, target, _now_iso()),
        )
        await conn.commit()


async def get_recent_actions(limit: int = 20) -> list:
    """آخرین اقدامات ادمین‌ها، جدیدترین اول — برای بخش «آمار»/بازبینی پنل ادمین."""
    async with app_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT admin_id, action, target, timestamp FROM admin_actions "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()

    columns = ("admin_id", "action", "target", "timestamp")
    return [dict(zip(columns, row)) for row in rows]
