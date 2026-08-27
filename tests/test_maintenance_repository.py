# tests/test_maintenance_repository.py
#
# فاز M1. فیکسچر عیناً هم‌الگو با
# test_equipment_repository.py: یک دیتابیس sqlite واقعی و موقت، schema
# دستی نوشته‌شده (نه فراخوانی setup_tables) — همان قرارداد تست‌های موجود
# این پروژه برای جدول‌های medical_device.db.

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import maintenance_repository as mr  # noqa: E402


@pytest.fixture
def temp_equipment_db(tmp_path, monkeypatch):
    db_path = tmp_path / "medical_device_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE device_maintenance_status (
            device_name TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE device_maintenance_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_name TEXT NOT NULL,
            item_key TEXT NOT NULL,
            content_type TEXT NOT NULL,
            text_content TEXT,
            file_id TEXT,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "EQUIPMENT_DB_PATH", str(db_path))
    return db_path


# --- setup_tables (تست جدا، روی یه دیتابیس کاملاً خالی/بدون فیکسچر بالا) ---

@pytest.mark.asyncio
async def test_setup_tables_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh.db"
    monkeypatch.setattr(config, "EQUIPMENT_DB_PATH", str(db_path))

    await mr.setup_tables()
    await mr.setup_tables()  # نباید خطا بدهد (CREATE TABLE IF NOT EXISTS)

    assert await mr.is_enabled("xray") is False


# --- is_enabled / set_enabled ---

@pytest.mark.asyncio
async def test_is_enabled_defaults_false_for_unknown_device(temp_equipment_db):
    assert await mr.is_enabled("xray") is False


@pytest.mark.asyncio
async def test_set_enabled_true_then_read_back(temp_equipment_db):
    await mr.set_enabled("xray", True)
    assert await mr.is_enabled("xray") is True


@pytest.mark.asyncio
async def test_set_enabled_is_idempotent_upsert(temp_equipment_db):
    """دو بار پشت‌سرهم True ست‌کردن نباید خطا بدهد یا ردیف تکراری بسازد."""
    await mr.set_enabled("xray", True)
    await mr.set_enabled("xray", True)
    assert await mr.is_enabled("xray") is True


@pytest.mark.asyncio
async def test_set_enabled_can_toggle_back_to_false(temp_equipment_db):
    await mr.set_enabled("xray", True)
    await mr.set_enabled("xray", False)
    assert await mr.is_enabled("xray") is False


@pytest.mark.asyncio
async def test_set_enabled_only_affects_given_device(temp_equipment_db):
    await mr.set_enabled("xray", True)
    assert await mr.is_enabled("mri") is False


# --- add_item / get_items / get_item_counts / display_order ---

@pytest.mark.asyncio
async def test_add_item_then_get_items_round_trip(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "خرابی یک", None)
    items = await mr.get_items("xray", "common_failures")
    assert items == [("text", "خرابی یک", None)]


@pytest.mark.asyncio
async def test_add_item_preserves_insertion_order_via_display_order(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "اول", None)
    await mr.add_item("xray", "common_failures", "photo", "دوم", "file_2")
    await mr.add_item("xray", "common_failures", "video", None, "file_3")

    items = await mr.get_items("xray", "common_failures")
    assert [i[1] for i in items] == ["اول", "دوم", None]
    assert items[2][2] == "file_3"


@pytest.mark.asyncio
async def test_get_items_only_returns_matching_device_and_item_key(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "برای ایکس‌ری", None)
    await mr.add_item("mri", "common_failures", "text", "برای ام‌آرآی", None)
    await mr.add_item("xray", "spare_parts", "text", "قطعه‌ی ایکس‌ری", None)

    items = await mr.get_items("xray", "common_failures")
    assert len(items) == 1
    assert items[0][1] == "برای ایکس‌ری"


@pytest.mark.asyncio
async def test_get_item_counts_groups_correctly(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "a", None)
    await mr.add_item("xray", "common_failures", "text", "b", None)
    await mr.add_item("xray", "spare_parts", "text", "c", None)

    counts = await mr.get_item_counts("xray")
    assert counts == {"common_failures": 2, "spare_parts": 1}


@pytest.mark.asyncio
async def test_get_item_counts_empty_for_device_with_no_items(temp_equipment_db):
    assert await mr.get_item_counts("xray") == {}


# --- get_populated_item_keys ---

@pytest.mark.asyncio
async def test_populated_item_keys_follows_catalog_order_not_insertion_order(temp_equipment_db):
    # ترتیب کاتالوگ: common_failures, troubleshooting, spare_parts, calibration
    await mr.add_item("xray", "calibration", "text", "a", None)
    await mr.add_item("xray", "common_failures", "text", "b", None)

    keys = await mr.get_populated_item_keys("xray")
    assert keys == ["common_failures", "calibration"]


@pytest.mark.asyncio
async def test_populated_item_keys_excludes_empty_sub_items(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "a", None)
    keys = await mr.get_populated_item_keys("xray")
    assert "spare_parts" not in keys
    assert "troubleshooting" not in keys


# --- has_any_content ---

@pytest.mark.asyncio
async def test_has_any_content_false_when_empty(temp_equipment_db):
    assert await mr.has_any_content("xray") is False


@pytest.mark.asyncio
async def test_has_any_content_true_after_add(temp_equipment_db):
    await mr.add_item("xray", "spare_parts", "text", "x", None)
    assert await mr.has_any_content("xray") is True


# --- clear_item ---

@pytest.mark.asyncio
async def test_clear_item_removes_all_items_in_that_sub_item(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "a", None)
    await mr.add_item("xray", "common_failures", "text", "b", None)

    await mr.clear_item("xray", "common_failures")

    assert await mr.get_items("xray", "common_failures") == []


@pytest.mark.asyncio
async def test_clear_item_does_not_touch_other_sub_items(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "a", None)
    await mr.add_item("xray", "spare_parts", "text", "b", None)

    await mr.clear_item("xray", "common_failures")

    assert await mr.get_items("xray", "spare_parts") != []


@pytest.mark.asyncio
async def test_clear_item_does_not_touch_other_devices(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "a", None)
    await mr.add_item("mri", "common_failures", "text", "b", None)

    await mr.clear_item("xray", "common_failures")

    assert await mr.get_items("mri", "common_failures") != []


@pytest.mark.asyncio
async def test_add_item_after_clear_restarts_display_order_cleanly(temp_equipment_db):
    """بعد از پاک‌کردن کامل، آیتم جدید باید دوباره اول لیست باشد (نه اینکه
    display_order قدیمی باعث ترتیب غلط شود)."""
    await mr.add_item("xray", "common_failures", "text", "قدیمی ۱", None)
    await mr.add_item("xray", "common_failures", "text", "قدیمی ۲", None)
    await mr.clear_item("xray", "common_failures")

    await mr.add_item("xray", "common_failures", "text", "جدید", None)

    items = await mr.get_items("xray", "common_failures")
    assert items == [("text", "جدید", None)]
