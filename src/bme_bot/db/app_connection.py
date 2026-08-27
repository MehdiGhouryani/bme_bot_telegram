# src/bme_bot/db/app_connection.py
#
# اتصال مستقل و async-safe به users.db (کاربران + محدودیت استفاده از AI).
# این دیتابیس عمداً کاملاً از medical_device.db جدا نگه داشته می‌شود؛ به همین
# دلیل یک ماژول اتصال اختصاصی برای هرکدام وجود دارد (این فایل برای users.db،
# و equipment_connection.py برای medical_device.db).
#
# استفاده از aiosqlite (نه sqlite3 استاندارد/sync) برای این‌که کوئری‌ها حلقه‌ی
# رویداد async را در طول اجرا مسدود نکنند.
#
# get_connection از _connection_factory.py می‌آید تا کد باز/بستن اتصال با
# equipment_connection.py تکرار نشود؛ خودِ دیتابیس همچنان کاملاً جدا و مستقل
# است.

import aiosqlite

from ._connection_factory import make_connection_getter
from .. import config

get_connection = make_connection_getter(lambda: config.USERS_DB_PATH)


async def setup_users_database():
    """جدول‌های users، ai_usage، ocr_usage، stt_usage، quiz_usage،
    jozve_usage، feature_limits، feature_usage و admin_actions را در صورت
    نبود می‌سازد (معادل setup_database قدیمی)."""
    async with get_connection() as conn:
        await conn.execute('''CREATE TABLE IF NOT EXISTS users
                          (user_id INTEGER PRIMARY KEY,
                           username TEXT,
                           chat_id TEXT)''')
        await conn.execute('''CREATE TABLE IF NOT EXISTS ai_usage
                          (user_id INTEGER PRIMARY KEY,
                           request_count INTEGER DEFAULT 0,
                           last_request_date TEXT)''')
        # جدول مستقل محدودیت OCR — عیناً همان شکل ai_usage، جدول جدا چون
        # سقف روزانه/معنای مصرف این دو فیچر متفاوت است (db/ocr_usage_repository.py).
        await conn.execute('''CREATE TABLE IF NOT EXISTS ocr_usage
                          (user_id INTEGER PRIMARY KEY,
                           request_count INTEGER DEFAULT 0,
                           last_request_date TEXT,
                           last_request_timestamp INTEGER DEFAULT 0)''')

        # جدول مستقل محدودیت STT (تبدیل ویس به متن) — عیناً همان شکل
        # ocr_usage، جدول جدا چون این دو فیچر معنای مصرف و سقف متفاوتی
        # دارند (db/stt_usage_repository.py).
        await conn.execute('''CREATE TABLE IF NOT EXISTS stt_usage
                          (user_id INTEGER PRIMARY KEY,
                           request_count INTEGER DEFAULT 0,
                           last_request_date TEXT,
                           last_request_timestamp INTEGER DEFAULT 0)''')

        # جدول مستقل محدودیت کوییز از متن (db/quiz_usage_repository.py).
        await conn.execute('''CREATE TABLE IF NOT EXISTS quiz_usage
                          (user_id INTEGER PRIMARY KEY,
                           request_count INTEGER DEFAULT 0,
                           last_request_date TEXT,
                           last_request_timestamp INTEGER DEFAULT 0)''')

        # جدول مستقل محدودیت ویس‌استاد-به-جزوه، عمداً سقف پایین‌تر
        # (db/jozve_usage_repository.py — دلیل کامل همان‌جا مستند شده).
        await conn.execute('''CREATE TABLE IF NOT EXISTS jozve_usage
                          (user_id INTEGER PRIMARY KEY,
                           request_count INTEGER DEFAULT 0,
                           last_request_date TEXT,
                           last_request_timestamp INTEGER DEFAULT 0)''')

        # منبع واحد سقف روزانه/کول‌داون هر فیچر، قابل‌تغییر از پنل ادمین
        # (db/feature_limits_repository.py). unit فقط برای stt برابر
        # 'seconds' است (بقیه 'count') — سقف STT بر مبنای مجموع مدت صدای
        # پردازش‌شده است، نه تعداد فایل.
        await conn.execute('''CREATE TABLE IF NOT EXISTS feature_limits
                          (feature_name TEXT PRIMARY KEY,
                           daily_limit INTEGER NOT NULL,
                           cooldown_seconds INTEGER NOT NULL,
                           unit TEXT NOT NULL DEFAULT 'count')''')
        # seed اولیه با INSERT OR IGNORE — اگر ادمین قبلاً از پنل مقداری را
        # عوض کرده، این‌جا هرگز رویش نوشته نمی‌شود (فقط ردیف نبود را پر می‌کند).
        for feature_name, daily_limit, cooldown_seconds, unit in (
            ("ai", 5, 60, "count"),
            ("ocr", 5, 60, "count"),
            ("stt", 300, 60, "seconds"),
            ("quiz", 5, 60, "count"),
            ("jozve", 1, 120, "count"),
        ):
            await conn.execute(
                "INSERT OR IGNORE INTO feature_limits "
                "(feature_name, daily_limit, cooldown_seconds, unit) VALUES (?, ?, ?, ?)",
                (feature_name, daily_limit, cooldown_seconds, unit),
            )

        # زیرساخت پنل ادمین.
        # feature_usage — یک ردیف به‌ازای هر تعامل مهم کاربر با یک بخش از ربات
        # (منبع خام برای بخش «آمار» پنل ادمین). detail برای جزئیات اختیاری است
        # (مثلاً کدام لایه‌ی AI/OCR پاسخ داد).
        await conn.execute('''CREATE TABLE IF NOT EXISTS feature_usage
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           user_id INTEGER NOT NULL,
                           feature TEXT NOT NULL,
                           detail TEXT,
                           timestamp TEXT NOT NULL)''')
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feature_usage_feature ON feature_usage(feature)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_feature_usage_timestamp ON feature_usage(timestamp)"
        )

        # admin_actions — لاگ اقدامات حساس ادمین (بن/آنبن، ارسال Broadcast) —
        # محافظت در برابر خطای انسانی (نه فقط ردیابی) است.
        await conn.execute('''CREATE TABLE IF NOT EXISTS admin_actions
                          (id INTEGER PRIMARY KEY AUTOINCREMENT,
                           admin_id INTEGER NOT NULL,
                           action TEXT NOT NULL,
                           target TEXT,
                           timestamp TEXT NOT NULL)''')

        # ستون‌های جدید (اگر قبلاً اضافه نشده) — عیناً همان الگوی last_request_timestamp
        for alter_statement in (
            "ALTER TABLE ai_usage ADD COLUMN last_request_timestamp INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN joined_at TEXT",
            "ALTER TABLE users ADD COLUMN last_seen_at TEXT",
        ):
            try:
                await conn.execute(alter_statement)
            except aiosqlite.OperationalError:
                pass

        await conn.commit()
