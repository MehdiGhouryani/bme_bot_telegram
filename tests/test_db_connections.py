# tests/test_db_connections.py
#
# تست‌های _connection_factory.py + یک تست رگرسیون مستقیم برای این‌که
# app_connection.py واقعاً aiosqlite را import کرده — setup_users_database
# از aiosqlite.OperationalError استفاده می‌کند (که فقط در دومین اجرا/بار دوم
# اجرای ربات، وقتی ستون از قبل وجود دارد، واقعاً اجرا می‌شود)، پس یک import
# گم‌شده اینجا فقط در ری‌استارت دوم ربات به‌شکل NameError دیده می‌شد، نه در
# اجرای اول.

import sys
from pathlib import Path

import aiosqlite
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db._connection_factory import make_connection_getter  # noqa: E402
from bme_bot.db.app_connection import setup_users_database  # noqa: E402
from bme_bot.db import app_connection, equipment_connection  # noqa: E402


@pytest.mark.asyncio
async def test_connection_factory_opens_and_closes(tmp_path):
    db_path = tmp_path / "factory_test.db"
    get_connection = make_connection_getter(lambda: str(db_path))

    async with get_connection() as conn:
        await conn.execute("CREATE TABLE t (x INTEGER)")
        await conn.commit()

    # اتصال باید بسته شده باشد؛ یک اتصال جدید باید بتواند به همان فایل وصل شود
    async with get_connection() as conn2:
        async with conn2.execute("SELECT COUNT(*) FROM t") as cursor:
            row = await cursor.fetchone()
            assert row[0] == 0


@pytest.mark.asyncio
async def test_connection_factory_picks_up_path_changes_dynamically(tmp_path, monkeypatch):
    """db_path_provider باید هر بار در لحظه‌ی فراخوانی خوانده شود، نه یک‌بار در
    زمان ساخت get_connection (وگرنه monkeypatch در تست‌های دیگر اثر نمی‌کرد)."""
    path_a = tmp_path / "a.db"
    path_b = tmp_path / "b.db"
    current = {"path": str(path_a)}
    get_connection = make_connection_getter(lambda: current["path"])

    async with get_connection() as conn:
        await conn.execute("CREATE TABLE marker (v TEXT)")
        await conn.execute("INSERT INTO marker VALUES ('a')")
        await conn.commit()

    current["path"] = str(path_b)
    async with get_connection() as conn:
        await conn.execute("CREATE TABLE marker (v TEXT)")
        await conn.execute("INSERT INTO marker VALUES ('b')")
        await conn.commit()

    async with aiosqlite.connect(path_a) as conn:
        async with conn.execute("SELECT v FROM marker") as cur:
            assert (await cur.fetchone())[0] == "a"
    async with aiosqlite.connect(path_b) as conn:
        async with conn.execute("SELECT v FROM marker") as cur:
            assert (await cur.fetchone())[0] == "b"


@pytest.mark.asyncio
async def test_app_and_equipment_connections_point_to_different_configured_paths(tmp_path, monkeypatch):
    """رگرسیون برای تصمیم محصولی «دو دیتابیس کاملاً جدا»: استفاده‌ی مشترک از
    کارخانه‌ی اتصال نباید باعث شود دو دیتابیس به یک فایل ختم شوند."""
    users_path = tmp_path / "users.db"
    equip_path = tmp_path / "medical_device.db"
    monkeypatch.setattr(config, "USERS_DB_PATH", str(users_path))
    monkeypatch.setattr(config, "EQUIPMENT_DB_PATH", str(equip_path))

    async with app_connection.get_connection() as conn:
        await conn.execute("CREATE TABLE only_in_users (x INTEGER)")
        await conn.commit()

    async with equipment_connection.get_connection() as conn:
        await conn.execute("CREATE TABLE only_in_equipment (x INTEGER)")
        await conn.commit()

    async with aiosqlite.connect(users_path) as conn:
        tables = [r[0] async for r in await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert "only_in_users" in tables
    assert "only_in_equipment" not in tables


@pytest.mark.asyncio
async def test_setup_users_database_is_idempotent(tmp_path, monkeypatch):
    """رگرسیون مستقیم برای باگ پیداشده: فراخوانی دوم setup_users_database
    (شبیه‌سازی ری‌استارت ربات روی یک دیتابیس موجود) نباید NameError بدهد —
    این دقیقاً همان مسیری است که ALTER TABLE با OperationalError مواجه می‌شود."""
    monkeypatch.setattr(config, "USERS_DB_PATH", str(tmp_path / "users.db"))

    await setup_users_database()  # اجرای اول: ستون جدید ساخته می‌شود
    await setup_users_database()  # اجرای دوم: ALTER TABLE با OperationalError مواجه می‌شود (باید بی‌صدا نادیده گرفته شود)
