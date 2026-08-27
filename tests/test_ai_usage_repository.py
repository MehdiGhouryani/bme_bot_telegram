# tests/test_ai_usage_repository.py
#
# تست منطق محدودیت روزانه و کول‌داون سوال از AI — همان منطق database.py
# قدیمی، حالا روی aiosqlite.
#
# سقف دیگر ثابت پایتون نیست — از جدول feature_limits خوانده می‌شود؛
# فیکسچر این فایل آن جدول را هم با seed واقعی (۵ در روز) می‌سازد.
# increment_ai_usage و record_attempt دو تابع جدا هستند - تست‌های زیر این
# تفکیک را صریحاً پوشش می‌دهند.

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import ai_usage_repository  # noqa: E402

AI_DAILY_LIMIT_SEED = 5
AI_COOLDOWN_SEED = 60


@pytest.fixture
def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE ai_usage (
            user_id INTEGER PRIMARY KEY,
            request_count INTEGER DEFAULT 0,
            last_request_date TEXT,
            last_request_timestamp INTEGER DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE feature_limits (
            feature_name TEXT PRIMARY KEY,
            daily_limit INTEGER NOT NULL,
            cooldown_seconds INTEGER NOT NULL,
            unit TEXT NOT NULL DEFAULT 'count'
        )"""
    )
    conn.execute(
        "INSERT INTO feature_limits (feature_name, daily_limit, cooldown_seconds, unit) VALUES (?, ?, ?, 'count')",
        ("ai", AI_DAILY_LIMIT_SEED, AI_COOLDOWN_SEED),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_first_time_user_is_allowed(temp_users_db):
    can_ask, message = await ai_usage_repository.check_ai_limit(12345)
    assert can_ask is True


@pytest.mark.asyncio
async def test_cooldown_blocks_immediate_second_request(temp_users_db):
    user_id = 999
    can_ask, _ = await ai_usage_repository.check_ai_limit(user_id)
    assert can_ask is True
    await ai_usage_repository.record_attempt(user_id)

    can_ask_again, message = await ai_usage_repository.check_ai_limit(user_id)
    assert can_ask_again is False
    assert "ثانیه" in message


@pytest.mark.asyncio
async def test_increment_without_record_attempt_does_not_trigger_cooldown(temp_users_db):
    """increment_ai_usage نباید last_request_timestamp را دست‌کاری
    کند — این مسئولیت جدا record_attempt است، تا کول‌داون حتی روی تلاش
    ناموفق (که increment صدا زده نمی‌شود ولی record_attempt چرا) هم اعمال شود."""
    user_id = 111
    await ai_usage_repository.check_ai_limit(user_id)
    await ai_usage_repository.increment_ai_usage(user_id)

    can_ask_again, _ = await ai_usage_repository.check_ai_limit(user_id)
    assert can_ask_again is True


@pytest.mark.asyncio
async def test_record_attempt_does_not_increment_daily_count(temp_users_db):
    """record_attempt فقط کول‌داون را ثبت می‌کند؛ سهمیه‌ی روزانه باید
    دست‌نخورده بماند تا تلاش‌های ناموفق سهمیه‌ی کاربر را کم نکنند."""
    user_id = 222
    await ai_usage_repository.check_ai_limit(user_id)
    await ai_usage_repository.record_attempt(user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM ai_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 0


@pytest.mark.asyncio
async def test_daily_limit_enforced_after_seed_requests(temp_users_db):
    user_id = 555
    # کول‌داون را با نوشتن مستقیم last_request_timestamp قدیمی دور می‌زنیم تا
    # فقط منطق «محدودیت روزانه» را جدا تست کنیم.
    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO ai_usage (user_id, request_count, last_request_date, last_request_timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, AI_DAILY_LIMIT_SEED, __import__("datetime").date.today().isoformat(), 0),
        )
        await conn.commit()

    can_ask, message = await ai_usage_repository.check_ai_limit(user_id)
    assert can_ask is False
    assert str(AI_DAILY_LIMIT_SEED) in message


@pytest.mark.asyncio
async def test_increment_then_check_reflects_new_count(temp_users_db):
    user_id = 777
    await ai_usage_repository.check_ai_limit(user_id)  # ایجاد ردیف اولیه
    await ai_usage_repository.increment_ai_usage(user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM ai_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_limit_is_read_from_feature_limits_table_not_hardcoded(temp_users_db):
    """رگرسیون‌گارد: اگه ادمین سقف رو از پنل عوض کنه، همون لحظه اعمال
    بشه - بدون نیاز به دیپلوی مجدد یا تغییر کد."""
    from bme_bot.db import feature_limits_repository

    await feature_limits_repository.set_daily_limit("ai", 1)
    user_id = 888

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO ai_usage (user_id, request_count, last_request_date, last_request_timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, 1, __import__("datetime").date.today().isoformat(), 0),
        )
        await conn.commit()

    can_ask, message = await ai_usage_repository.check_ai_limit(user_id)
    assert can_ask is False
    assert "1" in message
