# src/bme_bot/db/_connection_factory.py
#
# کارخانه‌ی مشترک برای ساخت تابع get_connection() یک دیتابیس aiosqlite.
#
# چرا این فایل جدا اضافه شد؟
# app_connection.py و equipment_connection.py هرکدام دقیقاً همین الگو (باز کردن
# اتصال aiosqlite + finally بستن آن) را با فقط تفاوت مسیر فایل تکرار می‌کردند.
# این ماژول آن کد تکراری را یک‌بار می‌نویسد؛ دو
# دیتابیس همچنان کاملاً جدا می‌مانند (فایل‌های متفاوت، ماژول‌های متفاوت، هرکدام
# با متغیر پیکربندی مسیر خودشان) — فقط خودِ «باز/بستن اتصال» مشترک شده، نه
# دیتابیس‌ها یا داده‌های‌شان.
#
# نام این فایل با _ شروع می‌شود چون یک جزئیات پیاده‌سازی داخلی پکیج db است، نه
# چیزی که handlers/services مستقیماً از آن import کنند (آن‌ها همچنان از
# app_connection.get_connection() / equipment_connection.get_connection()
# استفاده می‌کنند — امضای بیرونی این دو ماژول تغییری نکرده است).

import logging
from contextlib import asynccontextmanager
from typing import Callable

import aiosqlite

logger = logging.getLogger(__name__)

# مدت انتظار روی قفل SQLite قبل از خطای "database is locked". پیش‌فرض خودِ
# sqlite3 پایتون ۵ ثانیه است؛ این‌جا صریح و کمی بلندتر گذاشته شد تا هنگام
# هم‌زمانی گروه + چت خصوصی (+ broadcast/job روزانه) به‌جای خطا، کمی صبر شود.
_BUSY_TIMEOUT_SECONDS = 10.0

# مسیرهایی که WAL برایشان در این پردازش فعال شده. journal_mode=WAL داخل خود
# فایل دیتابیس ذخیره می‌شود (پایدار است)، پس تکرارش روی هر اتصال بی‌فایده
# است و فقط یک رفت‌وبرگشت اضافه به thread اتصال می‌زند.
_wal_enabled_paths: set[str] = set()


def make_connection_getter(db_path_provider: Callable[[], str], *, wal: bool = False):
    """یک context manager async می‌سازد که هر بار فراخوانی، یک اتصال aiosqlite
    تازه به مسیر برگردانده‌شده از db_path_provider() باز و در پایان می‌بندد.

    db_path_provider یک تابع است (نه یک رشته‌ی مسیر ثابت) تا اگر مقدار
    config.USERS_DB_PATH/EQUIPMENT_DB_PATH در زمان اجرا تغییر کند (مثلاً در
    تست‌ها با monkeypatch)، هر اتصال جدید مسیر به‌روز را ببیند، نه مسیری که در
    لحظه‌ی import منجمد شده باشد.

    wal=True: اولین اتصال به هر مسیر، journal_mode=WAL را فعال می‌کند تا
    خواننده‌ها نویسنده را بلاک نکنند (و برعکس). best-effort است: روی هر
    خطا (مثلاً فایل‌سیستم بدون پشتیبانی از shared-memory) بی‌صدا با حالت
    پیش‌فرض ادامه می‌دهد. توجه: در WAL کنار فایل .db فایل‌های -wal و -shm
    هم ساخته می‌شود؛ برای بکاپ باید از sqlite backup API (یا VACUUM INTO)
    استفاده کرد، نه کپی خام فقط خودِ .db در حین کار بات.
    """

    @asynccontextmanager
    async def get_connection():
        path = db_path_provider()
        conn = await aiosqlite.connect(path, timeout=_BUSY_TIMEOUT_SECONDS)
        try:
            if wal and path not in _wal_enabled_paths:
                try:
                    await conn.execute("PRAGMA journal_mode=WAL")
                    _wal_enabled_paths.add(path)
                except Exception as e:
                    logger.warning("could not enable WAL for %s: %s", path, e)
            yield conn
        finally:
            await conn.close()

    return get_connection
