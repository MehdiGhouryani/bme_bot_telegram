# tests/test_quiz_usage_repository.py
#
# تست محدودیت روزانه و کول‌داون کوییز.
#
# سقف روزانه دیگر ثابت پایتون نیست — از جدول feature_limits خوانده
# می‌شود؛ فیکسچر این فایل آن جدول را هم می‌سازد.

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import quiz_usage_repository  # noqa: E402

QUIZ_DAILY_LIMIT_SEED = 5
QUIZ_COOLDOWN_SEED = 60


@pytest.fixture
def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE quiz_usage (
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
        ("quiz", QUIZ_DAILY_LIMIT_SEED, QUIZ_COOLDOWN_SEED),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_first_time_user_is_allowed(temp_users_db):
    can_process, _ = await quiz_usage_repository.check_quiz_limit(12345)
    assert can_process is True


@pytest.mark.asyncio
async def test_cooldown_blocks_immediate_second_request(temp_users_db):
    user_id = 999
    can_process, _ = await quiz_usage_repository.check_quiz_limit(user_id)
    assert can_process is True
    await quiz_usage_repository.record_attempt(user_id)

    can_process_again, message = await quiz_usage_repository.check_quiz_limit(user_id)
    assert can_process_again is False
    assert "ثانیه" in message


@pytest.mark.asyncio
async def test_daily_limit_enforced_after_seed_requests(temp_users_db):
    user_id = 555
    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO quiz_usage (user_id, request_count, last_request_date, last_request_timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, QUIZ_DAILY_LIMIT_SEED, __import__("datetime").date.today().isoformat(), 0),
        )
        await conn.commit()

    can_process, message = await quiz_usage_repository.check_quiz_limit(user_id)
    assert can_process is False
    assert str(QUIZ_DAILY_LIMIT_SEED) in message


@pytest.mark.asyncio
async def test_increment_then_check_reflects_new_count(temp_users_db):
    user_id = 777
    await quiz_usage_repository.check_quiz_limit(user_id)
    await quiz_usage_repository.increment_quiz_usage(user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM quiz_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_record_attempt_does_not_increment_daily_count(temp_users_db):
    user_id = 222
    await quiz_usage_repository.check_quiz_limit(user_id)
    await quiz_usage_repository.record_attempt(user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM quiz_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 0
