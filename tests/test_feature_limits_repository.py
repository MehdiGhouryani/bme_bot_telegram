# tests/test_feature_limits_repository.py
#
# تست منبع واحد سقف روزانه/کول‌داون هر فیچر — get/set/get_all،
# و این‌که یک ردیف موجود دستی-ادمین با re-setup پاک نمی‌شود.

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import feature_limits_repository  # noqa: E402


@pytest.fixture
def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE feature_limits (
            feature_name TEXT PRIMARY KEY,
            daily_limit INTEGER NOT NULL,
            cooldown_seconds INTEGER NOT NULL,
            unit TEXT NOT NULL DEFAULT 'count'
        )"""
    )
    conn.execute(
        "INSERT INTO feature_limits (feature_name, daily_limit, cooldown_seconds, unit) VALUES (?, ?, ?, ?)",
        ("quiz", 5, 60, "count"),
    )
    conn.execute(
        "INSERT INTO feature_limits (feature_name, daily_limit, cooldown_seconds, unit) VALUES (?, ?, ?, ?)",
        ("stt", 300, 60, "seconds"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_get_limit_returns_stored_row(temp_users_db):
    daily_limit, cooldown_seconds, unit = await feature_limits_repository.get_limit("quiz")
    assert (daily_limit, cooldown_seconds, unit) == (5, 60, "count")


@pytest.mark.asyncio
async def test_get_limit_returns_seconds_unit_for_stt(temp_users_db):
    daily_limit, cooldown_seconds, unit = await feature_limits_repository.get_limit("stt")
    assert unit == "seconds"
    assert daily_limit == 300


@pytest.mark.asyncio
async def test_get_limit_falls_back_when_row_missing(temp_users_db):
    """اگه ردیف اصلاً نبود (مثلاً migration قدیمی)، باید fallback ایمن
    برگرده، نه استثنا بندازه."""
    daily_limit, cooldown_seconds, unit = await feature_limits_repository.get_limit("jozve")
    assert daily_limit > 0
    assert cooldown_seconds > 0


@pytest.mark.asyncio
async def test_set_daily_limit_updates_existing_row(temp_users_db):
    await feature_limits_repository.set_daily_limit("quiz", 2)
    daily_limit, cooldown_seconds, unit = await feature_limits_repository.get_limit("quiz")
    assert daily_limit == 2
    assert cooldown_seconds == 60  # دست‌نخورده مونده
    assert unit == "count"


@pytest.mark.asyncio
async def test_set_daily_limit_creates_row_if_missing(temp_users_db):
    """edge case: اگه ردیف نبود، set_daily_limit باید بسازدش، نه خطا بده."""
    await feature_limits_repository.set_daily_limit("jozve", 7)
    daily_limit, _cooldown, _unit = await feature_limits_repository.get_limit("jozve")
    assert daily_limit == 7


@pytest.mark.asyncio
async def test_get_all_limits_returns_every_row_sorted(temp_users_db):
    limits = await feature_limits_repository.get_all_limits()
    names = [item["feature_name"] for item in limits]
    assert names == sorted(names)
    assert {"quiz", "stt"}.issubset(set(names))


@pytest.mark.asyncio
async def test_set_daily_limit_does_not_affect_other_features(temp_users_db):
    await feature_limits_repository.set_daily_limit("quiz", 99)
    stt_limit, _, _ = await feature_limits_repository.get_limit("stt")
    assert stt_limit == 300
