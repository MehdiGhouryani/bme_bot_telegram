# src/bme_bot/db/maintenance_repository.py
#
# CRUD جدول‌های بخش «تعمیرات و نگهداری» (فاز M1/M2).
# در medical_device.db (نه users.db) چون این محتوا مال دانشنامه‌ی تجهیزاته، نه
# کاربر/مصرف — عیناً همان قانون جداسازی دو دیتابیسی که equipment_repository.py
# هم رعایت می‌کند؛ به همین دلیل از equipment_connection.py (نه app_connection.py)
# استفاده می‌شود.
#
# --- تصمیم کلیدی: ذخیره‌ی file_id تلگرام، نه بایت خام ---
# برخلاف ستون photo موجود در جدول information (که بایت خام JPEG را مستقیم در
# BLOB نگه می‌دارد — قابل قبول برای ۷۲ عکس ثابتِ import اولیه)، اینجا چون
# ادمین قرار است مدام و به‌مرور چندین عکس/ویدیو از *داخل تلگرام* بفرستد،
# طبق مستندات رسمی تلگرام (core.telegram.org/bots/api#sending-files):
# «اگر فایل قبلاً روی سرورهای تلگرام ذخیره شده، نیازی به آپلود دوباره نیست؛
# کافی‌ست file_id را پاس بدهید — برای فایل‌های ارسال‌شده به این روش هیچ
# محدودیتی وجود ندارد.» پس فقط همین رشته‌ی کوتاه ذخیره می‌شود، نه خودِ فایل —
# هم دیتابیس سبک می‌ماند (به‌خصوص برای ویدیو)، هم با فلسفه‌ی «رایگان» پروژه
# هم‌خوان است (خودِ تلگرام میزبان فایل می‌ماند).
#
# --- مدل حذف (تصمیم شما: نسخه‌ی ساده) ---
# حذف تک‌تک آیتم پشتیبانی نمی‌شود؛ فقط clear_item کل زیربخش را یکجا پاک
# می‌کند و ادمین از نو می‌فرستد.
#
# --- display_order ---
# چون تنها راه حذف، پاک‌کردن کامل زیربخش است (نه حذف تک آیتم)، هیچ‌وقت gap
# در شماره‌ها ایجاد نمی‌شود؛ پس add_item می‌تواند از COUNT(*) فعلی به‌عنوان
# display_order بعدی استفاده کند، بدون نیاز به MAX(display_order)+1.

from __future__ import annotations

from . import equipment_connection
from .. import maintenance_catalog


async def setup_tables() -> None:
    """جدول‌های device_maintenance_status و device_maintenance_items را در
    صورت نبود می‌سازد (هم‌الگو با app_connection.setup_users_database؛ از
    app._post_init فراخوانی می‌شود)."""
    async with equipment_connection.get_connection() as conn:
        await conn.execute('''CREATE TABLE IF NOT EXISTS device_maintenance_status
                          (device_name TEXT PRIMARY KEY,
                           enabled INTEGER NOT NULL DEFAULT 0)''')
        await conn.execute('''CREATE TABLE IF NOT EXISTS device_maintenance_items
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           device_name TEXT NOT NULL,
                           item_key TEXT NOT NULL,
                           content_type TEXT NOT NULL,
                           text_content TEXT,
                           file_id TEXT,
                           display_order INTEGER NOT NULL DEFAULT 0,
                           created_at TEXT NOT NULL DEFAULT (datetime('now')))''')
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_maintenance_items_lookup "
            "ON device_maintenance_items(device_name, item_key)"
        )
        await conn.commit()


async def is_enabled(device_name: str) -> bool:
    async with equipment_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT enabled FROM device_maintenance_status WHERE device_name = ?",
            (device_name,),
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])


async def set_enabled(device_name: str, enabled: bool) -> None:
    async with equipment_connection.get_connection() as conn:
        await conn.execute(
            "INSERT INTO device_maintenance_status (device_name, enabled) VALUES (?, ?) "
            "ON CONFLICT(device_name) DO UPDATE SET enabled = excluded.enabled",
            (device_name, int(enabled)),
        )
        await conn.commit()


async def get_item_counts(device_name: str) -> dict:
    """تعداد آیتم هر زیربخش برای یک دستگاه، فقط با یک کوئری (نه ۴ کوئری
    جدا). کلیدهایی که هیچ آیتمی ندارند اصلاً در دیکشنری برگشتی نیستند —
    فراخواننده باید برای آن‌ها ۰ فرض کند (get(item_key, 0))."""
    async with equipment_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT item_key, COUNT(*) FROM device_maintenance_items "
            "WHERE device_name = ? GROUP BY item_key",
            (device_name,),
        ) as cursor:
            rows = await cursor.fetchall()
            return {item_key: count for item_key, count in rows}


async def get_populated_item_keys(device_name: str) -> list:
    """کلیدهای زیربخش‌هایی که واقعاً حداقل یک آیتم دارند، به همان ترتیب
    فهرست ثابت (maintenance_catalog) — برای نمایش به کاربر عادی، طبق تصمیم
    شما، زیربخش خالی اصلاً نشان داده نمی‌شود."""
    counts = await get_item_counts(device_name)
    return [key for key, _ in maintenance_catalog.MAINTENANCE_ITEMS if counts.get(key, 0) > 0]


async def has_any_content(device_name: str) -> bool:
    async with equipment_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT 1 FROM device_maintenance_items WHERE device_name = ? LIMIT 1",
            (device_name,),
        ) as cursor:
            return (await cursor.fetchone()) is not None


async def get_items(device_name: str, item_key: str) -> list:
    """آیتم‌های یک زیربخش به ترتیب نمایش. هر آیتم: (content_type,
    text_content, file_id)."""
    async with equipment_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT content_type, text_content, file_id FROM device_maintenance_items "
            "WHERE device_name = ? AND item_key = ? ORDER BY display_order",
            (device_name, item_key),
        ) as cursor:
            return await cursor.fetchall()


async def add_item(
    device_name: str, item_key: str, content_type: str, text_content: str | None, file_id: str | None,
) -> None:
    """یک آیتم جدید به انتهای زیربخش اضافه می‌کند. item_key باید از قبل در
    maintenance_catalog.ITEM_KEYS معتبر شده باشد (فراخواننده مسئول است —
    همان الگوی equipment_repository.update_action_text که allow-list را قبل
    از فراخوانی چک می‌کند، نه اینجا با raise، چون اینجا item_key هرگز
    مستقیماً در متن کوئری استفاده نمی‌شود — فقط پارامتر، پس ریسک تزریق SQL
    بند ۳.۱ اصلاً مصداق ندارد؛ اعتبارسنجی صرفاً برای رد callback_data
    دستکاری‌شده لازم است، نه امنیت کوئری)."""
    async with equipment_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT COUNT(*) FROM device_maintenance_items WHERE device_name = ? AND item_key = ?",
            (device_name, item_key),
        ) as cursor:
            row = await cursor.fetchone()
            next_order = row[0] if row else 0

        await conn.execute(
            "INSERT INTO device_maintenance_items "
            "(device_name, item_key, content_type, text_content, file_id, display_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (device_name, item_key, content_type, text_content, file_id, next_order),
        )
        await conn.commit()


async def clear_item(device_name: str, item_key: str) -> None:
    """همه‌ی آیتم‌های یک زیربخش را یکجا پاک می‌کند (تصمیم شما: نسخه‌ی ساده،
    نه حذف تک‌تک)."""
    async with equipment_connection.get_connection() as conn:
        await conn.execute(
            "DELETE FROM device_maintenance_items WHERE device_name = ? AND item_key = ?",
            (device_name, item_key),
        )
        await conn.commit()
