# src/bme_bot/db/users_repository.py
#
# عملیات مربوط به جدول users. جایگزین save_user در database.py قدیمی.
#
# --- چرا save_user از ON CONFLICT صریح استفاده می‌کند، نه INSERT OR REPLACE ---
# INSERT OR REPLACE کل ردیف را حذف و دوباره می‌سازد. تا وقتی users فقط ۳ ستون
# داشت (user_id/username/chat_id) این بی‌ضرر بود چون همه‌ی ستون‌ها هربار
# دوباره مقداردهی می‌شدند؛ ولی start() به همین save_user در *هر* اجرای
# /start سر می‌زند (نه فقط بار اول) — یعنی با ستون‌های جدید (is_banned/
# joined_at) زیر همین INSERT OR REPLACE، یک کاربر بن‌شده با زدن دوباره‌ی
# /start بی‌صدا خودش را آنبن می‌کرد (چون is_banned به DEFAULT صفر برمی‌گشت)
# و joined_at واقعی‌اش هم پاک می‌شد. رفع: ON CONFLICT صریح که فقط
# username/chat_id را لمس می‌کند؛ is_banned/joined_at/last_seen_at
# دست‌نخورده می‌مانند مگر توابع اختصاصی خودشان (set_banned، touch_last_seen)
# صدا زده شوند.

from datetime import datetime, timezone

from . import app_connection


def _now_iso() -> str:
    """زمان فعلی UTC، به‌شکلی که مستقیماً با خروجی SQLite datetime() قابل‌مقایسه
    باشد.

    قبلاً از .isoformat() استفاده می‌شد که خروجی‌اش
    "2026-08-09T10:17:53.956565+00:00" است — با 'T' و پسوند timezone. ولی همه‌جا
    برای فیلتر «N روز اخیر» از خودِ SQLite استفاده می‌شود:
    `WHERE joined_at >= datetime('now', '-7 days')`، که فرمتش
    "2026-08-02 10:17:53" است — با فاصله، بدون پسوند. این دو رشته با هم مقایسه‌ی
    لغوی (lexicographic) می‌شوند؛ چون 'T' (0x54) از فاصله (0x20) در ASCII
    بزرگ‌تر است، هر رکوردی که تاریخش (نه لزوماً ساعتش) با آستانه یکی بیفتد،
    همیشه «بزرگ‌تر» ارزیابی می‌شود — صرف‌نظر از ساعت واقعی. با یک تست مستقیم
    روی SQLite واقعی تایید شد: رکوردی که همین‌الان ثبت شده، حتی با شرط
    `>= datetime('now', '+1 hour')` هم match می‌شد. تاثیرش روی همه‌ی بازه‌های
    N-روزه است (get_user_stats، send_daily_summary، سلامت سیستم)، بیشترین آسیب
    روی بازه‌های کوتاه (days=1) چون پهنای خطا تقریباً یک شبانه‌روز است. نام تابع
    (`_now_iso`) عمداً همان ماند تا فراخوان‌ها/importها دست‌نخورده بمانند —
    خروجی‌اش دیگر دقیقاً ISO 8601 نیست، ولی برای این پروژه UTC-محور بودنش کافی
    و مهم‌تر است.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


async def save_user(user_id, username, chat_id):
    """اطلاعات کاربر را ذخیره یا به‌روزرسانی می‌کند (معادل save_user قدیمی).

    فقط username/chat_id/joined_at (فقط بار اول) را دست می‌زند — is_banned و
    last_seen_at عمداً اینجا لمس نمی‌شوند (بالا را ببینید)."""
    async with app_connection.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username, chat_id, joined_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            username = ?,
            chat_id = ?
            """,
            (user_id, username, chat_id, _now_iso(), username, chat_id),
        )
        await conn.commit()


async def touch_last_seen(user_id):
    """last_seen_at کاربر را به «همین الان» به‌روز می‌کند. از global gate
    (app.py) برای *هر* تعامل کاربر با ربات صدا زده می‌شود — از جمله کاربرانی
    که هرگز /start نزده‌اند (مثلاً مستقیم از /ask استفاده کرده‌اند)، به همین
    دلیل از ON CONFLICT استفاده می‌شود تا برای چنین کاربری هم یک ردیف حداقلی
    ساخته شود، بدون دست‌زدن به is_banned/joined_at اگر از قبل وجود داشته باشند."""
    async with app_connection.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, last_seen_at)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            last_seen_at = ?
            """,
            (user_id, _now_iso(), _now_iso()),
        )
        await conn.commit()


async def is_banned(user_id) -> bool:
    """آیا این کاربر مسدود است؟ برای کاربری که اصلاً ردیفی ندارد، False
    برمی‌گرداند (کسی که هیچ‌وقت وجود نداشته، مسدود هم نیست)."""
    async with app_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT is_banned FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


async def set_banned(user_id, banned: bool):
    """وضعیت بن کاربر را ست می‌کند. اگر کاربر ردیفی نداشته باشد (نادر — یعنی
    ادمین با یک user_id کاملاً غریبه کار می‌کند)، یک ردیف حداقلی ساخته می‌شود."""
    async with app_connection.get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, is_banned)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            is_banned = ?
            """,
            (user_id, int(banned), int(banned)),
        )
        await conn.commit()


async def search_user(query: str):
    """جستجوی یک کاربر با user_id دقیق (اگر query عددی باشد) یا username
    (تطبیق جزئی/case-insensitive). حداکثر ۱۰ نتیجه برمی‌گرداند تا پیام تلگرام
    غیرقابل‌کنترل نشود. هر نتیجه یک dict با تمام ستون‌های users است."""
    query = query.strip().lstrip('@')

    async with app_connection.get_connection() as conn:
        if query.isdigit():
            sql = (
                "SELECT user_id, username, chat_id, is_banned, joined_at, last_seen_at "
                "FROM users WHERE user_id = ?"
            )
            params = (int(query),)
        else:
            sql = (
                "SELECT user_id, username, chat_id, is_banned, joined_at, last_seen_at "
                "FROM users WHERE username LIKE ? COLLATE NOCASE LIMIT 10"
            )
            params = (f"%{query}%",)

        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()

    columns = ("user_id", "username", "chat_id", "is_banned", "joined_at", "last_seen_at")
    return [dict(zip(columns, row)) for row in rows]


async def get_all_active_chat_ids() -> list:
    """chat_id تمام کاربران *غیرمسدود* را برمی‌گرداند — لیست مقصد Broadcast.
    کاربران بن‌شده عمداً حذف می‌شوند."""
    async with app_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT chat_id FROM users WHERE is_banned = 0 AND chat_id IS NOT NULL"
        ) as cursor:
            rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def get_user_stats() -> dict:
    """آمار کلی کاربران برای بخش «آمار» پنل ادمین: کل، جدید امروز/هفته/ماه،
    فعال ۷/۳۰ روز اخیر (بر پایه‌ی last_seen_at، نه feature_usage — چون
    last_seen_at با *هر* تعامل به‌روز می‌شود، نه فقط فیچرهای instrumented شده)."""
    async with app_connection.get_connection() as conn:
        async def _scalar(sql, params=()):
            async with conn.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

        total = await _scalar("SELECT COUNT(*) FROM users")
        new_today = await _scalar(
            "SELECT COUNT(*) FROM users WHERE joined_at >= datetime('now', '-1 day')"
        )
        new_week = await _scalar(
            "SELECT COUNT(*) FROM users WHERE joined_at >= datetime('now', '-7 days')"
        )
        new_month = await _scalar(
            "SELECT COUNT(*) FROM users WHERE joined_at >= datetime('now', '-30 days')"
        )
        active_7d = await _scalar(
            "SELECT COUNT(*) FROM users WHERE last_seen_at >= datetime('now', '-7 days')"
        )
        active_30d = await _scalar(
            "SELECT COUNT(*) FROM users WHERE last_seen_at >= datetime('now', '-30 days')"
        )
        banned = await _scalar("SELECT COUNT(*) FROM users WHERE is_banned = 1")

    return {
        "total": total,
        "new_today": new_today,
        "new_week": new_week,
        "new_month": new_month,
        "active_7d": active_7d,
        "active_30d": active_30d,
        "banned": banned,
    }
