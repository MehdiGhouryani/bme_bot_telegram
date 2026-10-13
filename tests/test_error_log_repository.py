# tests/test_error_log_repository.py

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import error_log_repository  # noqa: E402


@pytest.fixture
def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE error_log
                     (fingerprint TEXT PRIMARY KEY,
                      exception_type TEXT NOT NULL,
                      location TEXT NOT NULL,
                      count INTEGER NOT NULL DEFAULT 1,
                      first_seen TEXT NOT NULL,
                      last_seen TEXT NOT NULL,
                      sample_traceback TEXT NOT NULL)''')
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_record_error_first_occurrence_returns_count_one(temp_users_db):
    count = await error_log_repository.record_error(
        fingerprint="TypeError@x.py:1", exception_type="TypeError", location="x.py:1",
        traceback_text="Traceback...",
    )

    assert count == 1


@pytest.mark.asyncio
async def test_record_error_same_fingerprint_increments_count_not_new_row(temp_users_db):
    """رجوع به db/error_log_repository.py: یک ردیف به‌ازای هر اثرانگشتِ
    یکتا، نه هر رخداد — حتی رخداد دهم هم باید همون یک ردیف رو به‌روز کنه."""
    fp = "sqlite3.OperationalError@handlers/equipment_admin_edit.py:187"
    for _ in range(9):
        await error_log_repository.record_error(
            fingerprint=fp, exception_type="OperationalError", location="handlers/equipment_admin_edit.py:187",
            traceback_text="Traceback #N...",
        )
    final_count = await error_log_repository.record_error(
        fingerprint=fp, exception_type="OperationalError", location="handlers/equipment_admin_edit.py:187",
        traceback_text="Traceback #10...",
    )

    assert final_count == 10
    conn = sqlite3.connect(temp_users_db)
    rows = conn.execute("SELECT COUNT(*) FROM error_log WHERE fingerprint = ?", (fp,)).fetchall()
    conn.close()
    assert rows == [(1,)]  # یک ردیف، نه ده تا


@pytest.mark.asyncio
async def test_record_error_keeps_original_sample_traceback_not_latest(temp_users_db):
    """نمونه‌ی traceback باید از رخداد *اول* بمونه — رخداد صدم چیز جدیدی
    اضافه نمی‌کنه، پس بازنویسی‌اش فقط context مفید اولیه رو گم می‌کنه."""
    fp = "TypeError@x.py:1"
    await error_log_repository.record_error(
        fingerprint=fp, exception_type="TypeError", location="x.py:1", traceback_text="نمونه‌ی اصلی و مفید",
    )
    await error_log_repository.record_error(
        fingerprint=fp, exception_type="TypeError", location="x.py:1", traceback_text="نمونه‌ی بی‌ارزش بعدی",
    )

    errors = await error_log_repository.get_recent_errors()

    assert errors[0]["sample_traceback"] == "نمونه‌ی اصلی و مفید"


@pytest.mark.asyncio
async def test_different_fingerprints_get_separate_rows(temp_users_db):
    await error_log_repository.record_error(
        fingerprint="TypeError@a.py:1", exception_type="TypeError", location="a.py:1", traceback_text="t1",
    )
    await error_log_repository.record_error(
        fingerprint="ValueError@b.py:2", exception_type="ValueError", location="b.py:2", traceback_text="t2",
    )

    errors = await error_log_repository.get_recent_errors()

    assert len(errors) == 2


@pytest.mark.asyncio
async def test_get_recent_errors_orders_newest_first_and_respects_limit(temp_users_db):
    import asyncio

    for i in range(5):
        await error_log_repository.record_error(
            fingerprint=f"TypeError@f{i}.py:1", exception_type="TypeError", location=f"f{i}.py:1",
            traceback_text=f"t{i}",
        )
        await asyncio.sleep(0.01)  # تضمین last_seen متمایز برای تست ترتیب

    errors = await error_log_repository.get_recent_errors(limit=3)

    assert len(errors) == 3
    assert errors[0]["location"] == "f4.py:1"  # آخرین ثبت‌شده، اول لیست


@pytest.mark.asyncio
async def test_get_recent_errors_empty_when_no_errors_logged(temp_users_db):
    assert await error_log_repository.get_recent_errors() == []
