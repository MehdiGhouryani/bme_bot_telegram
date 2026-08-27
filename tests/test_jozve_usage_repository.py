# tests/test_jozve_usage_repository.py
#
# تست محدودیت روزانه و کول‌داون جزوه‌سازی.
#
# سقف دیگر ثابت پایتون نیست — از جدول feature_limits خوانده می‌شود. seed
# این فایل عمداً سخت‌گیرانه‌تر از OCR/STT/کوییز است (۱/روز، کول‌داون ۱۲۰
# ثانیه)، طبق تحلیل سهمیه‌ی TPD روزانه‌ی Groq (رجوع به README.md).

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import jozve_usage_repository  # noqa: E402

JOZVE_DAILY_LIMIT_SEED = 1
JOZVE_COOLDOWN_SEED = 120


@pytest.fixture
def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE jozve_usage (
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
        ("jozve", JOZVE_DAILY_LIMIT_SEED, JOZVE_COOLDOWN_SEED),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


def test_seed_limits_are_stricter_than_ocr_stt_quiz():
    """رگرسیون‌گارد: این اعداد باید همچنان پایین‌تر از بقیه seed بشن تو
    app_connection.py، حتی اگه از پنل ادمین قابل‌تغییر شدن."""
    assert JOZVE_DAILY_LIMIT_SEED == 1
    assert JOZVE_COOLDOWN_SEED == 120


@pytest.mark.asyncio
async def test_first_time_user_is_allowed(temp_users_db):
    can_process, _ = await jozve_usage_repository.check_jozve_limit(12345)
    assert can_process is True


@pytest.mark.asyncio
async def test_cooldown_blocks_immediate_second_request(temp_users_db):
    user_id = 999
    await jozve_usage_repository.check_jozve_limit(user_id)
    await jozve_usage_repository.record_attempt(user_id)

    can_process_again, message = await jozve_usage_repository.check_jozve_limit(user_id)
    assert can_process_again is False
    assert "ثانیه" in message


@pytest.mark.asyncio
async def test_daily_limit_enforced_after_seed_requests(temp_users_db):
    user_id = 555
    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO jozve_usage (user_id, request_count, last_request_date, last_request_timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, JOZVE_DAILY_LIMIT_SEED, __import__("datetime").date.today().isoformat(), 0),
        )
        await conn.commit()

    can_process, message = await jozve_usage_repository.check_jozve_limit(user_id)
    assert can_process is False
    assert str(JOZVE_DAILY_LIMIT_SEED) in message


@pytest.mark.asyncio
async def test_increment_then_check_reflects_new_count(temp_users_db):
    user_id = 777
    await jozve_usage_repository.check_jozve_limit(user_id)
    await jozve_usage_repository.increment_jozve_usage(user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM jozve_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 1


@pytest.mark.asyncio
async def test_admin_can_raise_limit_from_panel(temp_users_db):
    """رگرسیون‌گارد: تغییر از پنل باید بدون دیپلوی مجدد اعمال بشه."""
    from bme_bot.db import feature_limits_repository

    await feature_limits_repository.set_daily_limit("jozve", 5)
    user_id = 321

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO jozve_usage (user_id, request_count, last_request_date, last_request_timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, 3, __import__("datetime").date.today().isoformat(), 0),
        )
        await conn.commit()

    can_process, _ = await jozve_usage_repository.check_jozve_limit(user_id)
    assert can_process is True  # با سقف قدیمی (۱) رد می‌شد، با سقف جدید (۵) نه
