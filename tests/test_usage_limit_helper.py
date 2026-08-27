# tests/test_usage_limit_helper.py
#
# تست منطق مشترک شمارشی (بین ai/ocr/quiz/jozve) — و اینکه allow-list
# جدول جلوی table_name غیرمجاز رو می‌گیره (محافظت دفاعی، دلیلش در خودِ
# usage_limit_helper.py مستند شده).

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import usage_limit_helper  # noqa: E402


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
        "INSERT INTO feature_limits (feature_name, daily_limit, cooldown_seconds, unit) VALUES ('quiz', 3, 60, 'count')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_check_limit_uses_feature_limits_value(temp_users_db):
    can_process, _ = await usage_limit_helper.check_limit("quiz_usage", "quiz", 111)
    assert can_process is True


@pytest.mark.asyncio
async def test_daily_limit_enforced_via_shared_helper(temp_users_db):
    user_id = 222
    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO quiz_usage (user_id, request_count, last_request_date, last_request_timestamp) "
            "VALUES (?, 3, ?, 0)",
            (user_id, __import__("datetime").date.today().isoformat()),
        )
        await conn.commit()

    can_process, message = await usage_limit_helper.check_limit("quiz_usage", "quiz", user_id)
    assert can_process is False
    assert "3" in message


def test_disallowed_table_name_raises_value_error():
    with pytest.raises(ValueError):
        usage_limit_helper._validate_table("users; DROP TABLE users;--")


def test_disallowed_table_name_is_rejected_even_if_plausible():
    """جدول واقعی ولی خارج از دامنه‌ی این هلپر (مثلاً stt_usage که منطق
    جداگانه‌ی خودش رو داره) هم نباید قبول بشه."""
    with pytest.raises(ValueError):
        usage_limit_helper._validate_table("stt_usage")


@pytest.mark.asyncio
async def test_check_limit_rejects_disallowed_table(temp_users_db):
    with pytest.raises(ValueError):
        await usage_limit_helper.check_limit("not_a_real_table", "quiz", 1)


@pytest.mark.asyncio
async def test_record_attempt_and_increment_rejects_disallowed_table(temp_users_db):
    with pytest.raises(ValueError):
        await usage_limit_helper.record_attempt("not_a_real_table", 1)
    with pytest.raises(ValueError):
        await usage_limit_helper.increment_usage("not_a_real_table", 1)


@pytest.mark.asyncio
async def test_increment_usage_via_shared_helper(temp_users_db):
    user_id = 333
    await usage_limit_helper.check_limit("quiz_usage", "quiz", user_id)
    await usage_limit_helper.increment_usage("quiz_usage", user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM quiz_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 1
