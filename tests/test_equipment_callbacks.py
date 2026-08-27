# tests/test_equipment_callbacks.py
#
# تست‌های سطح هندلر برای equipment_callbacks.py — با آبجکت‌های جعلی سبک‌وزن
# (نه کل کتابخانه‌ی تلگرام). دو محور اصلی:
# - اعتبارسنجی device/line در برابر درخت واقعی (نه فقط اعتماد به callback_data کاربر)
# - ترتیب امن ارسال عکس/حذف پیام قبلی در مسیر «معرفی دستگاه»

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config, equipment_tree  # noqa: E402
from bme_bot.handlers import equipment_callbacks  # noqa: E402


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
        """CREATE TABLE information (
            name TEXT PRIMARY KEY, definition TEXT, photo TEXT, types TEXT, structure TEXT,
            operation TEXT, related_technologies TEXT, advantages_disadvantages TEXT, safety TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO information VALUES (?,?,?,?,?,?,?,?,?)",
        ("xray", "تعریف اشعه ایکس", "PHOTO123", "انواع", "ساختار", "عملکرد", "تک مشابه", "مزایا", "ایمنی"),
    )
    # فاز M2: handle_device_click حالا maintenance_callbacks.with_maintenance_button
    # را هم صدا می‌زند که این دو جدول را می‌خواند — در تولید با
    # app._post_init/setup_maintenance_tables ساخته می‌شوند؛ اینجا دستی.
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


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.answers = []
        self.deleted = False
        self.edited_text = None
        self.edited_reply_markup = None

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def delete_message(self):
        self.deleted = True

    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        self.edited_text = text
        self.edited_reply_markup = reply_markup

    async def edit_message_reply_markup(self, reply_markup=None):
        pass


class FakeBot:
    def __init__(self, photo_should_fail=False):
        self.photo_should_fail = photo_should_fail
        self.sent_photos = []
        self.sent_messages = []

    async def send_photo(self, chat_id, photo, caption=None, parse_mode=None, reply_markup=None):
        if self.photo_should_fail:
            raise RuntimeError("simulated Telegram API failure (e.g. invalid file_id)")
        self.sent_photos.append((chat_id, photo, caption, reply_markup))

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        self.sent_messages.append((chat_id, text))


def make_update(query, bot):
    return SimpleNamespace(
        callback_query=query,
        effective_chat=SimpleNamespace(id=111),
        effective_user=SimpleNamespace(id=42),
    )


def make_context(bot):
    return SimpleNamespace(bot=bot, user_data={})


# --- یافته‌ی ۲: اعتبارسنجی device/line ---

@pytest.mark.asyncio
async def test_valid_device_and_line_is_accepted(temp_equipment_db):
    query = FakeQuery("xray:structure:imaging_devices")
    bot = FakeBot()
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert query.edited_text == "ساختار"
    assert not query.answers  # هیچ پیام خطایی نباید باشد


@pytest.mark.asyncio
async def test_fabricated_line_is_rejected_even_with_real_device_and_action(temp_equipment_db):
    """دستگاه و اکشن واقعی‌اند، ولی line ساختگی است (مثلاً از یک callback_data
    دستکاری‌شده) — نباید هیچ کیبورد/کوئری‌ای بر مبنای این line ساختگی بسازیم."""
    query = FakeQuery("xray:structure:this_menu_does_not_exist")
    bot = FakeBot()
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert query.edited_text is None
    assert query.answers and "یافت نشد" in query.answers[0][0]


@pytest.mark.asyncio
async def test_fabricated_device_is_rejected_even_with_real_line_and_action(temp_equipment_db):
    query = FakeQuery("totally_fake_device:structure:imaging_devices")
    bot = FakeBot()
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert query.edited_text is None
    assert query.answers and "یافت نشد" in query.answers[0][0]


@pytest.mark.asyncio
async def test_malformed_callback_data_without_enough_colons_is_rejected(temp_equipment_db):
    query = FakeQuery("xray")  # فقط یک تکه، نه سه‌تکه
    bot = FakeBot()
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert query.answers and "نامعتبر" in query.answers[0][0]


# --- یافته‌ی ۵: ترتیب امن ارسال عکس ---

@pytest.mark.asyncio
async def test_definition_photo_success_deletes_old_message(temp_equipment_db):
    query = FakeQuery("xray:definition:imaging_devices")
    bot = FakeBot(photo_should_fail=False)
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert bot.sent_photos, "عکس باید ارسال شده باشد"
    assert query.deleted is True, "پیام قبلی فقط پس از ارسال موفق باید حذف شود"


@pytest.mark.asyncio
async def test_definition_photo_failure_does_not_delete_old_message(temp_equipment_db):
    """یافته‌ی ۵: اگر send_photo شکست بخورد، پیام قبلی نباید حذف شود — کاربر
    باید همچنان کیبورد قبلی را داشته باشد، نه یک پیام گمشده."""
    query = FakeQuery("xray:definition:imaging_devices")
    bot = FakeBot(photo_should_fail=True)
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert not bot.sent_photos
    assert query.deleted is False, "پیام قبلی نباید حذف شود چون ارسال عکس شکست خورد"
    assert query.answers and query.answers[0][1] is True  # show_alert=True


# --- ثبت آمار برای پنل ادمین ---

@pytest.mark.asyncio
async def test_device_click_logs_feature_usage(temp_equipment_db, monkeypatch):
    from unittest.mock import AsyncMock

    from bme_bot.db import feature_usage_repository

    log_usage_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_usage_mock)

    query = FakeQuery("xray")
    bot = FakeBot()
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_click(update, context, "xray")

    log_usage_mock.assert_awaited_once_with(42, "equipment", detail="xray")


# --- دکمه‌ی ویرایش ادمین ---

def _button_texts(markup):
    return [btn.text for row in markup.inline_keyboard for btn in row]


def _find_button(markup, callback_data):
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data == callback_data:
                return btn
    return None


@pytest.mark.asyncio
async def test_admin_sees_edit_button_on_text_action(temp_equipment_db, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])  # همان effective_user.id در make_update
    query = FakeQuery("xray:structure:imaging_devices")
    bot = FakeBot()
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert "✏️ ویرایش این متن" in _button_texts(query.edited_reply_markup)
    assert _find_button(query.edited_reply_markup, "admin_edit_field:xray:structure:imaging_devices")


@pytest.mark.asyncio
async def test_non_admin_does_not_see_edit_button(temp_equipment_db, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])  # effective_user.id=42 در لیست نیست
    query = FakeQuery("xray:structure:imaging_devices")
    bot = FakeBot()
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert "✏️ ویرایش این متن" not in _button_texts(query.edited_reply_markup)


@pytest.mark.asyncio
async def test_admin_sees_edit_button_on_definition_photo_view(temp_equipment_db, monkeypatch):
    """پوشش مسیر عکس الزامی بود — این‌جا هم دکمه باید ظاهر شود، نه فقط در
    شش اکشن متنی."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])
    query = FakeQuery("xray:definition:imaging_devices")
    bot = FakeBot()
    update = make_update(query, bot)
    context = make_context(bot)

    await equipment_callbacks.handle_device_action(update, context, query.data)

    assert bot.sent_photos
    _, _, _, reply_markup = bot.sent_photos[0]
    assert _find_button(reply_markup, "admin_edit_field:xray:definition:imaging_devices")
