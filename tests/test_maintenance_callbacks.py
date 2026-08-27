# tests/test_maintenance_callbacks.py
#
# فاز M2. آبجکت‌های جعلی سبک‌وزن، هم‌الگو با
# test_equipment_callbacks.py.

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config, equipment_tree  # noqa: E402
from bme_bot.db import maintenance_repository as mr  # noqa: E402
from bme_bot.handlers import maintenance_callbacks as mc  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_tree_cache():
    equipment_tree._TREE = None
    yield
    equipment_tree._TREE = None


@pytest.fixture
def temp_equipment_db(tmp_path, monkeypatch):
    db_path = tmp_path / "medical_device_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE device_maintenance_status (
            device_name TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE device_maintenance_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_name TEXT NOT NULL, item_key TEXT NOT NULL,
            content_type TEXT NOT NULL, text_content TEXT, file_id TEXT,
            display_order INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "EQUIPMENT_DB_PATH", str(db_path))
    return db_path


@pytest.fixture(autouse=True)
def _admin(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])


class FakeQuery:
    def __init__(self, data, chat_id=111):
        self.data = data
        self.answers = []
        self.edited_text = None
        self.edited_reply_markup = None
        self.message = SimpleNamespace(chat_id=chat_id)

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None):
        self.edited_text = text
        self.edited_reply_markup = reply_markup


class FakeBot:
    def __init__(self):
        self.sent_messages = []
        self.sent_photos = []
        self.sent_videos = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent_messages.append((chat_id, text, reply_markup))

    async def send_photo(self, chat_id, photo, caption=None):
        self.sent_photos.append((chat_id, photo, caption))

    async def send_video(self, chat_id, video, caption=None):
        self.sent_videos.append((chat_id, video, caption))


def _callback_update(query, user_id=1, bot=None):
    return SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=user_id), bot=bot or FakeBot())


def _context(bot=None):
    return SimpleNamespace(bot=bot or FakeBot())


def _flatten(markup):
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


_BASE_MARKUP = InlineKeyboardMarkup([[InlineKeyboardButton("انواع دستگاه", callback_data="xray:types:imaging_devices")]])


# --- with_maintenance_button ---

@pytest.mark.asyncio
async def test_admin_always_gets_manage_button_even_if_disabled(temp_equipment_db):
    result = await mc.with_maintenance_button(_BASE_MARKUP, "xray", user_id=42)
    callback_datas = _flatten(result)
    assert "maint_admin_open:xray" in callback_datas


@pytest.mark.asyncio
async def test_regular_user_gets_no_button_when_disabled(temp_equipment_db):
    await mr.add_item("xray", "spare_parts", "text", "x", None)  # محتوا هست ولی enabled نیست
    result = await mc.with_maintenance_button(_BASE_MARKUP, "xray", user_id=1)
    assert result is _BASE_MARKUP  # هیچ ردیفی اضافه نشد


@pytest.mark.asyncio
async def test_regular_user_gets_no_button_when_enabled_but_empty(temp_equipment_db):
    await mr.set_enabled("xray", True)
    result = await mc.with_maintenance_button(_BASE_MARKUP, "xray", user_id=1)
    assert result is _BASE_MARKUP


@pytest.mark.asyncio
async def test_regular_user_gets_view_button_when_enabled_and_populated(temp_equipment_db):
    await mr.set_enabled("xray", True)
    await mr.add_item("xray", "spare_parts", "text", "x", None)

    result = await mc.with_maintenance_button(_BASE_MARKUP, "xray", user_id=1)

    callback_datas = _flatten(result)
    assert "maint_view_open:xray" in callback_datas
    assert "maint_admin_open:xray" not in callback_datas


@pytest.mark.asyncio
async def test_with_maintenance_button_preserves_existing_rows(temp_equipment_db):
    result = await mc.with_maintenance_button(_BASE_MARKUP, "xray", user_id=42)
    callback_datas = _flatten(result)
    assert "xray:types:imaging_devices" in callback_datas  # ردیف اصلی دست‌نخورده


# --- route: maint_view_open ---

@pytest.mark.asyncio
async def test_view_open_rejects_fabricated_device(temp_equipment_db):
    query = FakeQuery("maint_view_open:not_real")
    await mc.route(_callback_update(query), _context(), query.data)
    assert query.answers[0][1] is True


@pytest.mark.asyncio
async def test_view_open_alerts_when_nothing_populated(temp_equipment_db):
    await mr.set_enabled("xray", True)  # فعال ولی خالی (نباید عملاً پیش بیاید، محافظ دفاعی)
    query = FakeQuery("maint_view_open:xray")
    await mc.route(_callback_update(query), _context(), query.data)
    assert query.answers[0][1] is True


@pytest.mark.asyncio
async def test_view_open_lists_only_populated_sub_items_in_catalog_order(temp_equipment_db):
    await mr.add_item("xray", "calibration", "text", "a", None)
    await mr.add_item("xray", "common_failures", "text", "b", None)
    query = FakeQuery("maint_view_open:xray")

    await mc.route(_callback_update(query), _context(), query.data)

    callback_datas = _flatten(query.edited_reply_markup)
    assert callback_datas[:2] == ["maint_view_item:xray:common_failures", "maint_view_item:xray:calibration"]
    assert callback_datas[-1] == "xray"  # دکمه‌ی بازگشت، عیناً callback دستگاه


# --- route: maint_view_item ---

@pytest.mark.asyncio
async def test_view_item_malformed_data_rejected(temp_equipment_db):
    query = FakeQuery("maint_view_item:xray")  # فقط ۲ تکه
    await mc.route(_callback_update(query), _context(), query.data)
    assert query.answers[0][1] is True


@pytest.mark.asyncio
async def test_view_item_rejects_invalid_item_key(temp_equipment_db):
    query = FakeQuery("maint_view_item:xray:not_real_key")
    await mc.route(_callback_update(query), _context(), query.data)
    assert query.answers[0][1] is True


@pytest.mark.asyncio
async def test_view_item_alerts_when_empty(temp_equipment_db):
    query = FakeQuery("maint_view_item:xray:common_failures")
    await mc.route(_callback_update(query), _context(), query.data)
    assert query.answers[0][1] is True


@pytest.mark.asyncio
async def test_view_item_sends_each_item_as_separate_message(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "متن اول", None)
    await mr.add_item("xray", "common_failures", "photo", "کپشن", "file_abc")
    await mr.add_item("xray", "common_failures", "video", None, "file_xyz")
    bot = FakeBot()
    query = FakeQuery("maint_view_item:xray:common_failures", chat_id=111)

    await mc.route(_callback_update(query, bot=bot), _context(bot=bot), query.data)

    assert bot.sent_messages[0] == (111, "متن اول", None)
    assert bot.sent_photos == [(111, "file_abc", "کپشن")]
    assert bot.sent_videos == [(111, "file_xyz", None)]


@pytest.mark.asyncio
async def test_view_item_sends_trailing_back_button(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "متن", None)
    bot = FakeBot()
    query = FakeQuery("maint_view_item:xray:common_failures", chat_id=111)

    await mc.route(_callback_update(query, bot=bot), _context(bot=bot), query.data)

    last_message = bot.sent_messages[-1]
    assert last_message[0] == 111
    assert _flatten(last_message[2]) == ["xray"]
