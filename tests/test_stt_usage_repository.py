# tests/test_stt_usage_repository.py
#
# تست محدودیت روزانه (بر مبنای ثانیه، نه تعداد) و کول‌داون STT.
#
# سقف بر مبنای ثانیه است، نه تعداد — از feature_limits خوانده می‌شود؛
# فیکسچر این فایل آن جدول را هم می‌سازد (seed: ۳۰۰ ثانیه = ۵ دقیقه). امضای
# check_stt_limit/increment_stt_usage شامل duration_seconds است.

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import stt_usage_repository  # noqa: E402

STT_DAILY_LIMIT_SECONDS_SEED = 300  # ۵ دقیقه
STT_COOLDOWN_SEED = 60


@pytest.fixture
def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE stt_usage (
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
        "INSERT INTO feature_limits (feature_name, daily_limit, cooldown_seconds, unit) VALUES (?, ?, ?, 'seconds')",
        ("stt", STT_DAILY_LIMIT_SECONDS_SEED, STT_COOLDOWN_SEED),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_first_time_user_is_allowed(temp_users_db):
    can_process, _ = await stt_usage_repository.check_stt_limit(12345, duration_seconds=30)
    assert can_process is True


@pytest.mark.asyncio
async def test_cooldown_blocks_immediate_second_request(temp_users_db):
    user_id = 999
    can_process, _ = await stt_usage_repository.check_stt_limit(user_id, duration_seconds=30)
    assert can_process is True
    await stt_usage_repository.record_attempt(user_id)

    can_process_again, message = await stt_usage_repository.check_stt_limit(user_id, duration_seconds=30)
    assert can_process_again is False
    assert "ثانیه" in message


@pytest.mark.asyncio
async def test_increment_without_record_attempt_does_not_trigger_cooldown(temp_users_db):
    user_id = 111
    await stt_usage_repository.check_stt_limit(user_id, duration_seconds=30)
    await stt_usage_repository.increment_stt_usage(user_id, duration_seconds=30)

    can_process_again, _ = await stt_usage_repository.check_stt_limit(user_id, duration_seconds=30)
    assert can_process_again is True


@pytest.mark.asyncio
async def test_record_attempt_does_not_increment_daily_seconds(temp_users_db):
    user_id = 222
    await stt_usage_repository.check_stt_limit(user_id, duration_seconds=30)
    await stt_usage_repository.record_attempt(user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM stt_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 0


@pytest.mark.asyncio
async def test_daily_limit_enforced_when_cumulative_seconds_exceed_seed(temp_users_db):
    user_id = 555
    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO stt_usage (user_id, request_count, last_request_date, last_request_timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, STT_DAILY_LIMIT_SECONDS_SEED, __import__("datetime").date.today().isoformat(), 0),
        )
        await conn.commit()

    can_process, message = await stt_usage_repository.check_stt_limit(user_id, duration_seconds=1)
    assert can_process is False
    assert "دقیقه" in message


@pytest.mark.asyncio
async def test_single_file_longer_than_daily_limit_rejected_for_new_user(temp_users_db):
    """اولین باری که کاربر STT استفاده می‌کنه، اگه خودِ همون یه فایل از سقف
    روزانه بیشتر باشه، باید رد بشه - نه این‌که چون ردیفی وجود نداشت قبول بشه."""
    can_process, message = await stt_usage_repository.check_stt_limit(
        777, duration_seconds=STT_DAILY_LIMIT_SECONDS_SEED + 60,
    )
    assert can_process is False
    assert "دقیقه" in message


@pytest.mark.asyncio
async def test_increment_then_check_reflects_cumulative_seconds(temp_users_db):
    user_id = 888
    await stt_usage_repository.check_stt_limit(user_id, duration_seconds=30)
    await stt_usage_repository.increment_stt_usage(user_id, duration_seconds=45)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM stt_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 45


@pytest.mark.asyncio
async def test_two_files_summing_past_limit_rejected_on_second(temp_users_db):
    """سقف بر مبنای *مجموع* ثانیه‌ی امروزه - دو فایل که تک‌تک زیر سقفن ولی
    مجموعشون رد می‌شه، باید تو فایل دوم رد بشه."""
    user_id = 654
    can_process_1, _ = await stt_usage_repository.check_stt_limit(user_id, duration_seconds=200)
    assert can_process_1 is True
    await stt_usage_repository.increment_stt_usage(user_id, duration_seconds=200)

    can_process_2, message = await stt_usage_repository.check_stt_limit(user_id, duration_seconds=200)
    assert can_process_2 is False
    assert "دقیقه" in message
