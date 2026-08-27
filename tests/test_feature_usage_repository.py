# tests/test_feature_usage_repository.py
#
# تست منطق ثبت/تجمیع آمار استفاده (feature_usage) — منبع خام بخش
# «آمار» پنل ادمین.

import sys
from pathlib import Path

import pytest
import pytest_asyncio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import app_connection, feature_usage_repository  # noqa: E402


@pytest_asyncio.fixture
async def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    await app_connection.setup_users_database()
    return db_path


@pytest.mark.asyncio
async def test_log_usage_then_get_feature_counts(temp_users_db):
    await feature_usage_repository.log_usage(1, "equipment")
    await feature_usage_repository.log_usage(2, "equipment")
    await feature_usage_repository.log_usage(3, "ai")

    counts = await feature_usage_repository.get_feature_counts()

    assert counts == {"equipment": 2, "ai": 1}


@pytest.mark.asyncio
async def test_get_feature_counts_empty_when_no_usage(temp_users_db):
    counts = await feature_usage_repository.get_feature_counts()
    assert counts == {}


@pytest.mark.asyncio
async def test_log_usage_never_raises_even_on_bad_db_path(monkeypatch, tmp_path):
    """طبق مستندسازی خودِ تابع: خطای ثبت آمار نباید هرگز جریان اصلی هندلر را
    بترکاند. اینجا با یک مسیر دیتابیس نامعتبر (پوشه‌ی ناموجود) شبیه‌سازی
    می‌شود."""
    monkeypatch.setattr(config, "USERS_DB_PATH", str(tmp_path / "no" / "such" / "dir" / "db.sqlite"))

    await feature_usage_repository.log_usage(1, "equipment")  # نباید استثنایی بیندازد


@pytest.mark.asyncio
async def test_get_detail_breakdown_for_provider_stats(temp_users_db):
    """کاربرد اصلی detail: کدام لایه‌ی AI/OCR چند بار پاسخ داده."""
    await feature_usage_repository.log_usage(1, "ai", detail="gemini")
    await feature_usage_repository.log_usage(2, "ai", detail="gemini")
    await feature_usage_repository.log_usage(3, "ai", detail="groq")
    await feature_usage_repository.log_usage(4, "ocr", detail="google")  # فیچر متفاوت

    breakdown = await feature_usage_repository.get_detail_breakdown("ai")

    assert breakdown == {"gemini": 2, "groq": 1}


@pytest.mark.asyncio
async def test_stored_timestamp_format_is_sqlite_comparable(temp_users_db):
    """رگرسیون — همان باگ/تست users_repository.py، اینجا برای log_usage.
    اگر فرمت ذخیره‌شده ISO پایتون باشد (با 'T')، با خروجی SQLite datetime()
    که get_feature_counts/get_detail_breakdown برای فیلتر days استفاده
    می‌کنند ناسازگار می‌شود — یک رکورد «همین‌الان» حتی در برابر آستانه‌ی «یک
    ساعت در آینده» هم اشتباهاً match می‌شود."""
    import aiosqlite

    await feature_usage_repository.log_usage(1, "ai")

    async with aiosqlite.connect(str(temp_users_db)) as conn:
        async with conn.execute(
            "SELECT COUNT(*) FROM feature_usage WHERE user_id = 1 "
            "AND timestamp >= datetime('now', '+1 hour')"
        ) as cursor:
            row = await cursor.fetchone()

    assert row[0] == 0, (
        "رکوردی که همین الان ثبت شده نباید با آستانه‌ی «یک ساعت در آینده» "
        "match شود — اگر ۱ باشد یعنی فرمت timestamp دوباره ناسازگار شده."
    )


@pytest.mark.asyncio
async def test_get_feature_counts_respects_days_window(temp_users_db):
    import aiosqlite

    await feature_usage_repository.log_usage(1, "ai")  # همین الان — باید در پنجره باشد

    # یک ردیف قدیمی (۱۰ روز پیش) دستی درج می‌شود تا پنجره‌ی زمانی تست شود
    async with aiosqlite.connect(str(temp_users_db)) as conn:
        await conn.execute(
            "INSERT INTO feature_usage (user_id, feature, detail, timestamp) VALUES (?, ?, ?, datetime('now', '-10 days'))",
            (2, "ai", None),
        )
        await conn.commit()

    recent_counts = await feature_usage_repository.get_feature_counts(days=7)
    all_time_counts = await feature_usage_repository.get_feature_counts(days=None)

    assert recent_counts["ai"] == 1  # فقط ردیف تازه
    assert all_time_counts["ai"] == 2  # هردو ردیف
