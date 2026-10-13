# tests/test_settings_repository.py
#
# تست منبع واحد و عمومی تنظیمات (bot_settings) — get/set رشته‌ای و بولی،
# و این‌که ON CONFLICT (که این‌جا برخلاف equipment_repository کاملاً امنه
# چون خودمون جدول رو با PRIMARY KEY واقعی ساختیم) واقعاً UPDATE می‌کنه نه
# دو ردیف جدا.

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import settings_repository  # noqa: E402


@pytest.fixture
def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE bot_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_get_setting_returns_default_when_key_missing(temp_users_db):
    assert await settings_repository.get_setting("missing_key", "پیش‌فرض") == "پیش‌فرض"


@pytest.mark.asyncio
async def test_set_then_get_setting_roundtrips(temp_users_db):
    await settings_repository.set_setting("greeting", "سلام دنیا")

    assert await settings_repository.get_setting("greeting", "پیش‌فرض") == "سلام دنیا"


@pytest.mark.asyncio
async def test_set_setting_twice_updates_in_place_not_duplicate_rows(temp_users_db):
    await settings_repository.set_setting("greeting", "نسخه‌ی اول")
    await settings_repository.set_setting("greeting", "نسخه‌ی دوم")

    conn = sqlite3.connect(temp_users_db)
    rows = conn.execute("SELECT value FROM bot_settings WHERE key = ?", ("greeting",)).fetchall()
    conn.close()

    assert rows == [("نسخه‌ی دوم",)]


@pytest.mark.asyncio
async def test_bool_setting_roundtrips_true_and_false(temp_users_db):
    assert await settings_repository.get_bool_setting("flag", default=True) is True

    await settings_repository.set_bool_setting("flag", False)
    assert await settings_repository.get_bool_setting("flag", default=True) is False

    await settings_repository.set_bool_setting("flag", True)
    assert await settings_repository.get_bool_setting("flag", default=False) is True
