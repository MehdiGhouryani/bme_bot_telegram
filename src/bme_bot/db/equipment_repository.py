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
    """
    async with equipment_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT definition, photo FROM information WHERE name = ?", (device,)
        ) as cursor:
            return await cursor.fetchone()


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
    """متن یک ستون/اکشن مشخص را برای یک دستگاه به‌روزرسانی می‌کند (دکمه‌ی
    ویرایش ادمین).

    برخلاف get_definition_with_photo، اینجا هم (مثل get_action_text) `action`
    مستقیماً نام ستون است، نه یک مقدار پارامتری — همان کلاس آسیب‌پذیری SQL
    injection بالا این‌جا هم صدق می‌کند و باید همان allow-list قبل از ساخت
    کوئری چک شود؛ عمداً یک ValueError raise می‌کند (نه یک بازگشت بی‌صدا مثل
    get_action_text) چون فراخواننده (یک ادمین که آگاهانه در حال ویرایش است)
    باید از رد شدن مطلع شود، نه این‌که فکر کند ذخیره موفق بوده.
    """
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"'{action}' یک اکشن مجاز نیست.")

    async with equipment_connection.get_connection() as conn:
        await conn.execute(
            f"UPDATE information SET {action} = ? WHERE name = ?", (new_text, device)
        )
        await conn.commit()
