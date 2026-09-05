# src/bme_bot/db/equipment_repository.py
#
# تمام کوئری‌های جدول information (محتوای تجهیزات) اینجا و فقط اینجا نوشته
# می‌شوند — یک نقطه‌ی واحد و قابل‌ممیزی برای دسترسی به این داده.
#
# *** یادداشت امنیتی: چرا action همیشه در برابر allow-list چک می‌شود ***
# `action` از callback_data کلاینت تلگرام می‌آید و بعداً مستقیماً به‌عنوان نام
# ستون با f-string در کوئری قرار می‌گیرد (SQLite پارامتر جای‌گذاری‌شده برای
# نام ستون پشتیبانی نمی‌کند). تلگرام هیچ تضمینی نمی‌دهد که callback_data
# واقعاً از دکمه‌ای که ربات ساخته آمده باشد — بدون این چک، این یک
# آسیب‌پذیری SQL Injection واقعی است، نه فرضی. رفع: `action` همیشه پیش از
# استفاده در برابر ALLOWED_ACTIONS اعتبارسنجی می‌شود؛ اگر مقدار در این لیست
# نباشد، هیچ کوئری‌ای ساخته یا اجرا نمی‌شود.
#
# ALLOWED_ACTIONS مستقیماً از equipment_tree.get_allowed_actions() می‌آید —
# تنها منبع حقیقت — نه یک frozenset جداگانه‌ی هاردکد اینجا، تا از
# device_detail_template در equipment_menu.json هیچ‌وقت out-of-sync نشود
# (یک اکشن جدید در JSON بدون به‌روزرسانی یک لیست جدا، همیشه بی‌صدا رد
# می‌شد). equipment_tree.py عمداً یک ماژول خالص (بدون telegram) است تا این
# لایه‌ی دیتابیس مجبور نباشد از لایه‌ی UI (keyboards/menu_builder.py)
# import کند.

from . import equipment_connection
from .. import equipment_tree

ALLOWED_ACTIONS = equipment_tree.get_allowed_actions()


async def get_definition_with_photo(device: str):
    """برای اکشن 'definition' که علاوه بر متن، عکس هم برمی‌گرداند.

    ستون‌های این کوئری ثابت و در کد نوشته شده‌اند (نه از ورودی کاربر) پس نیازی
    به اعتبارسنجی allow-list ندارد؛ فقط `device` به‌صورت پارامتر (نه در متن
    کوئری) استفاده می‌شود.

    None برمی‌گرداند هم وقتی device اصلاً وجود ندارد، هم وقتی وجود دارد ولی
    definition و photo هردو خالی/NULL‌اند — قبلاً فقط حالت اول را در نظر
    می‌گرفت: fetchone() برای یک ردیف موجود با هر دو ستون NULL، تاپل
    (None, None) برمی‌گرداند که خودش truthy است، پس چک `if not result` در
    equipment_callbacks.handle_device_action هیچ‌وقت این حالت را نمی‌گرفت
    و به‌جایش سعی می‌کرد با photo=None یک عکس بفرستد (که در تلگرام واقعی
    شکست می‌خورد و به‌جای پیام «هنوز محتوایی نداره»، «سرویس موقتاً در
    دسترس نیست» نشان می‌داد — گمراه‌کننده، چون مشکل سرویس نبود، صرفاً
    محتوایی برای نشان‌دادن وجود نداشت)."""
    async with equipment_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT definition, photo FROM information WHERE name = ?", (device,)
        ) as cursor:
            row = await cursor.fetchone()

    if row is None or (not row[0] and not row[1]):
        return None
    return row


async def get_action_text(device: str, action: str):
    """متن یک ستون/اکشن مشخص را برای یک دستگاه برمی‌گرداند.

    اگر `action` در ALLOWED_ACTIONS نباشد، None برمی‌گردد بدون اینکه اصلاً
    کوئری‌ای ساخته شود.
    """
    if action not in ALLOWED_ACTIONS:
        return None

    async with equipment_connection.get_connection() as conn:
        async with conn.execute(
            f"SELECT {action} FROM information WHERE name = ?", (device,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def update_action_text(device: str, action: str, new_text: str) -> None:
    """متن یک ستون/اکشن مشخص را برای یک دستگاه جایگزین می‌کند (دکمه‌ی
    ویرایش ادمین) — همیشه جایگزینی کامل، نه الحاق.

    برخلاف get_definition_with_photo، اینجا هم (مثل get_action_text) `action`
    مستقیماً نام ستون است، نه یک مقدار پارامتری — همان کلاس آسیب‌پذیری SQL
    injection بالا این‌جا هم صدق می‌کند و باید همان allow-list قبل از ساخت
    کوئری چک شود؛ عمداً یک ValueError raise می‌کند (نه یک بازگشت بی‌صدا مثل
    get_action_text) چون فراخواننده (یک ادمین که آگاهانه در حال ویرایش است)
    باید از رد شدن مطلع شود، نه این‌که فکر کند ذخیره موفق بوده.

    اگر device وجود نداشته باشد، ردیفش ساخته می‌شود (نه فقط UPDATE خالص):
    قبلاً اگر ردیف device اصلاً وجود نداشت، UPDATE بی‌سروصدا ۰ ردیف را
    تغییر می‌داد — ادمین پیام «✅ ذخیره شد» را می‌دید ولی هیچ‌چیز واقعاً
    ذخیره نشده بود. این حالت با UI فعلی (دکمه‌ی ✏️ حالا حتی برای فیلد
    خالی/بدون‌ردیف هم رندر می‌شود، equipment_callbacks.handle_device_action
    را ببینید) عملاً قابل‌دسترس شده، پس دیگر یک حالت نظری/غیرقابل‌وقوع نیست.

    عمداً SELECT-then-branch است، نه `INSERT ... ON CONFLICT ... DO UPDATE`:
    نسخه‌ی قبلی از ON CONFLICT استفاده می‌کرد که فرض می‌کرد ستون name یک
    PRIMARY KEY/UNIQUE واقعی دارد؛ رو دیتابیس production واقعی این فرض غلط
    از آب درآمد (جدول واقعی چنین قیدی روی name نداشت) و هر ویرایش با
    `sqlite3.OperationalError: ON CONFLICT clause does not match any
    PRIMARY KEY or UNIQUE constraint` کرش می‌کرد — یک لاگ production واقعی
    این را تایید کرد. این نسخه هیچ فرضی درباره‌ی قید دیتابیس نمی‌کند، پس
    مستقل از schema واقعی کار می‌کند."""
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"'{action}' یک اکشن مجاز نیست.")

    async with equipment_connection.get_connection() as conn:
        async with conn.execute("SELECT 1 FROM information WHERE name = ?", (device,)) as cursor:
            exists = await cursor.fetchone() is not None

        if exists:
            await conn.execute(
                f"UPDATE information SET {action} = ? WHERE name = ?", (new_text, device)
            )
        else:
            await conn.execute(
                f"INSERT INTO information (name, {action}) VALUES (?, ?)", (device, new_text)
            )
        await conn.commit()
