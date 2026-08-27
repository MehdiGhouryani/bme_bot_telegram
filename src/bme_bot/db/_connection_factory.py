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

from contextlib import asynccontextmanager
from typing import Callable

import aiosqlite


def make_connection_getter(db_path_provider: Callable[[], str]):
    """یک context manager async می‌سازد که هر بار فراخوانی، یک اتصال aiosqlite
    تازه به مسیر برگردانده‌شده از db_path_provider() باز و در پایان می‌بندد.

    db_path_provider یک تابع است (نه یک رشته‌ی مسیر ثابت) تا اگر مقدار
    config.USERS_DB_PATH/EQUIPMENT_DB_PATH در زمان اجرا تغییر کند (مثلاً در
    تست‌ها با monkeypatch)، هر اتصال جدید مسیر به‌روز را ببیند، نه مسیری که در
    لحظه‌ی import منجمد شده باشد.
    """

    @asynccontextmanager
    async def get_connection():
        conn = await aiosqlite.connect(db_path_provider())
        try:
            yield conn
        finally:
            await conn.close()

    return get_connection
