# tests/test_ocr_usage_repository.py
#
# تست منطق محدودیت روزانه و کول‌داون OCR.
#
# سقف روزانه دیگر ثابت پایتون نیست — از جدول feature_limits خوانده
# می‌شود؛ فیکسچر این فایل آن جدول را هم می‌سازد. تست قدیمی «OCR باید
# پایین‌تر از AI باشد» حذف شد چون با اعداد فعلی (هر دو ۵) دیگر فرضش برقرار
# نیست - آن مقایسه خودش قابل‌تنظیم از پنل ادمین شده، نه یک رابطه‌ی ثابت در
# کد.

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import ocr_usage_repository  # noqa: E402

OCR_DAILY_LIMIT_SEED = 5
OCR_COOLDOWN_SEED = 60


@pytest.fixture
def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE ocr_usage (
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
        ("ocr", OCR_DAILY_LIMIT_SEED, OCR_COOLDOWN_SEED),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_first_time_user_is_allowed(temp_users_db):
    can_process, _ = await ocr_usage_repository.check_ocr_limit(12345)
    assert can_process is True


@pytest.mark.asyncio
async def test_cooldown_blocks_immediate_second_request(temp_users_db):
    user_id = 999
    can_process, _ = await ocr_usage_repository.check_ocr_limit(user_id)
    assert can_process is True
    await ocr_usage_repository.record_attempt(user_id)

    can_process_again, message = await ocr_usage_repository.check_ocr_limit(user_id)
    assert can_process_again is False
    assert "ثانیه" in message


@pytest.mark.asyncio
async def test_increment_without_record_attempt_does_not_trigger_cooldown(temp_users_db):
    """increment_ocr_usage دیگر last_request_timestamp را دست‌کاری نمی‌کند —
    این مسئولیت جدا record_attempt است، تا کول‌داون حتی روی تلاشی که با
    OcrProviderError شکست می‌خورد (که increment صدا زده نمی‌شود ولی
    record_attempt چرا) هم اعمال شود."""
    user_id = 111
    await ocr_usage_repository.check_ocr_limit(user_id)
    await ocr_usage_repository.increment_ocr_usage(user_id)

    can_process_again, _ = await ocr_usage_repository.check_ocr_limit(user_id)
    assert can_process_again is True


@pytest.mark.asyncio
async def test_record_attempt_does_not_increment_daily_count(temp_users_db):
    user_id = 222
    await ocr_usage_repository.check_ocr_limit(user_id)
    await ocr_usage_repository.record_attempt(user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM ocr_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 0


@pytest.mark.asyncio
async def test_daily_limit_enforced_after_seed_requests(temp_users_db):
    user_id = 555
    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO ocr_usage (user_id, request_count, last_request_date, last_request_timestamp) "
            "VALUES (?, ?, ?, ?)",
            (user_id, OCR_DAILY_LIMIT_SEED, __import__("datetime").date.today().isoformat(), 0),
        )
        await conn.commit()

    can_process, message = await ocr_usage_repository.check_ocr_limit(user_id)
    assert can_process is False
    assert str(OCR_DAILY_LIMIT_SEED) in message


@pytest.mark.asyncio
async def test_increment_then_check_reflects_new_count(temp_users_db):
    user_id = 777
    await ocr_usage_repository.check_ocr_limit(user_id)  # ایجاد ردیف اولیه
    await ocr_usage_repository.increment_ocr_usage(user_id)

    import aiosqlite

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT request_count FROM ocr_usage WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    assert row[0] == 1
