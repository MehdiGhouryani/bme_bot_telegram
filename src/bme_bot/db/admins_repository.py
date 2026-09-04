# src/bme_bot/db/admins_repository.py
#
# ادمین‌های اضافه‌شده از داخل بات توسط ادمین اصلی — مکمل فهرست استاتیک
# config.ADMIN_CHAT_ID (که فقط با ویرایش .env + ریستارت عوض می‌شه). این
# مخزن فقط لایه‌ی خام دیتابیسه؛ منطق «چه کسی ادمینه» و cache حافظه‌ای برای
# جلوگیری از async-کردن is_admin() سراسر کدبیس، تو utils/admin.py هست —
# نگاه کنید به کامنت آنجا برای توضیح کامل تصمیم.

from datetime import datetime, timezone

from . import app_connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def add_admin(user_id: int, added_by: int) -> None:
    """ادمین جدید اضافه می‌کند (idempotent — اگر از قبل بود، فقط added_by/
    added_at رو به‌روز می‌کنه، خطا نمی‌ده)."""
    async with app_connection.get_connection() as conn:
        await conn.execute(
            "INSERT INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET added_by = ?, added_at = ?",
            (user_id, added_by, _now_iso(), added_by, _now_iso()),
        )
        await conn.commit()


async def remove_admin(user_id: int) -> bool:
    """حذف می‌کند؛ True اگر واقعاً ردیفی حذف شد (یعنی از قبل ادمین دینامیک
    بود)، False اگر اصلاً نبود."""
    async with app_connection.get_connection() as conn:
        cursor = await conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await conn.commit()
        return cursor.rowcount > 0


async def list_admins() -> list[dict]:
    """همه‌ی ادمین‌های دینامیک، قدیمی‌ترین اول (ترتیب افزوده‌شدن)."""
    async with app_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT user_id, added_by, added_at FROM admins ORDER BY added_at ASC"
        ) as cursor:
            rows = await cursor.fetchall()

    columns = ("user_id", "added_by", "added_at")
    return [dict(zip(columns, row)) for row in rows]
