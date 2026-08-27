# tests/test_maintenance_admin_edit.py
#
# فاز M1. آبجکت‌های جعلی سبک‌وزن، هم‌الگو با
# test_equipment_admin_edit.py؛ دیتابیس واقعی و موقت برای maintenance_repository
# (نه mock)، عیناً همان قرارداد تست‌های موجود این پروژه.

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ConversationHandler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config, equipment_tree  # noqa: E402
from bme_bot.db import admin_actions_repository, maintenance_repository as mr  # noqa: E402
from bme_bot.handlers import maintenance_admin_edit as mae  # noqa: E402


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


class FakeQuery:
    def __init__(self, data, chat_id=111, message_id=555):
        self.data = data
        self.answers = []
        self.edited_text = None
        self.edited_reply_markup = None
        self.message = SimpleNamespace(chat_id=chat_id, message_id=message_id)

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, reply_markup=None):
        self.edited_text = text
        self.edited_reply_markup = reply_markup

    async def edit_message_reply_markup(self, reply_markup=None):
        self.edited_reply_markup = reply_markup


class FakeBot:
    def __init__(self):
        self.sent_messages = []
        self.edited_texts = []

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent_messages.append((chat_id, text, reply_markup))

    async def edit_message_text(self, chat_id, message_id, text, reply_markup=None):
        self.edited_texts.append((chat_id, message_id, text, reply_markup))


def _callback_update(query, user_id=42):
    return SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=user_id))


def _message_update(user_id=42, chat_id=111, text=None, photo=None, video=None, caption=None):
    message = SimpleNamespace(text=text, photo=photo, video=video, caption=caption, reply_text=AsyncMock())
    return SimpleNamespace(
        message=message, effective_user=SimpleNamespace(id=user_id), effective_chat=SimpleNamespace(id=chat_id),
    )


def _context(bot=None, user_data=None):
    return SimpleNamespace(bot=bot or FakeBot(), user_data=user_data if user_data is not None else {})


def _flatten(markup):
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def _button_texts(markup):
    return [btn.text for row in markup.inline_keyboard for btn in row]


@pytest.fixture(autouse=True)
def _admin(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])


@pytest.fixture(autouse=True)
def _log_action_mock(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr(admin_actions_repository, "log_action", mock)
    return mock


# --- start_admin_menu ---

@pytest.mark.asyncio
async def test_non_admin_cannot_open_admin_menu(temp_equipment_db, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    query = FakeQuery("maint_admin_open:xray")
    result = await mae.start_admin_menu(_callback_update(query, user_id=42), _context())

    assert result == ConversationHandler.END
    assert query.answers[0][1] is True


@pytest.mark.asyncio
async def test_fabricated_device_rejected(temp_equipment_db):
    query = FakeQuery("maint_admin_open:not_a_real_device")
    result = await mae.start_admin_menu(_callback_update(query), _context())

    assert result == ConversationHandler.END
    assert "یافت نشد" in query.answers[0][0]


@pytest.mark.asyncio
async def test_valid_open_shows_disabled_status_and_empty_counts(temp_equipment_db):
    query = FakeQuery("maint_admin_open:xray")
    result = await mae.start_admin_menu(_callback_update(query), _context())

    assert result == mae.MENU
    assert "غیرفعال" in query.edited_text
    button_texts = _button_texts(query.edited_reply_markup)
    assert any("خالی" in t for t in button_texts)
    callback_datas = _flatten(query.edited_reply_markup)
    assert "maint_admin_toggle:xray" in callback_datas
    assert "maint_admin_item:xray:common_failures" in callback_datas
    assert "maint_admin_exit:xray" in callback_datas


@pytest.mark.asyncio
async def test_valid_open_shows_enabled_status_and_item_counts(temp_equipment_db):
    await mr.set_enabled("xray", True)
    await mr.add_item("xray", "spare_parts", "text", "قطعه", None)
    query = FakeQuery("maint_admin_open:xray")

    await mae.start_admin_menu(_callback_update(query), _context())

    assert "فعال ✅" in query.edited_text
    button_texts = _button_texts(query.edited_reply_markup)
    assert any("1 آیتم" in t for t in button_texts)


# --- toggle_enabled ---

@pytest.mark.asyncio
async def test_toggle_enabled_turns_on_and_logs(temp_equipment_db, _log_action_mock):
    query = FakeQuery("maint_admin_toggle:xray")
    result = await mae.toggle_enabled(_callback_update(query), _context())

    assert result == mae.MENU
    assert await mr.is_enabled("xray") is True
    _log_action_mock.assert_awaited_once_with(42, "toggle_maintenance", target="xray:on")


@pytest.mark.asyncio
async def test_toggle_enabled_turns_off_when_already_on(temp_equipment_db):
    await mr.set_enabled("xray", True)
    query = FakeQuery("maint_admin_toggle:xray")

    await mae.toggle_enabled(_callback_update(query), _context())

    assert await mr.is_enabled("xray") is False


@pytest.mark.asyncio
async def test_toggle_enabled_rejects_fabricated_device(temp_equipment_db):
    query = FakeQuery("maint_admin_toggle:not_real")
    result = await mae.toggle_enabled(_callback_update(query), _context())
    assert result == ConversationHandler.END


# --- show_item_menu ---

@pytest.mark.asyncio
async def test_show_item_menu_malformed_data_rejected(temp_equipment_db):
    query = FakeQuery("maint_admin_item:xray")  # فقط ۲ تکه
    result = await mae.show_item_menu(_callback_update(query), _context())
    assert result == ConversationHandler.END
    assert "یافت نشد" in query.answers[0][0]


@pytest.mark.asyncio
async def test_show_item_menu_invalid_item_key_rejected(temp_equipment_db):
    query = FakeQuery("maint_admin_item:xray:not_a_real_key")
    result = await mae.show_item_menu(_callback_update(query), _context())
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_show_item_menu_no_clear_button_when_empty(temp_equipment_db):
    query = FakeQuery("maint_admin_item:xray:common_failures")
    result = await mae.show_item_menu(_callback_update(query), _context())

    assert result == mae.MENU
    callback_datas = _flatten(query.edited_reply_markup)
    assert not any(cd.startswith("maint_admin_clear_ask:") for cd in callback_datas)
    assert "maint_admin_add:xray:common_failures:text" in callback_datas


@pytest.mark.asyncio
async def test_show_item_menu_has_clear_button_when_populated(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "یک خرابی", None)
    query = FakeQuery("maint_admin_item:xray:common_failures")

    await mae.show_item_menu(_callback_update(query), _context())

    callback_datas = _flatten(query.edited_reply_markup)
    assert "maint_admin_clear_ask:xray:common_failures" in callback_datas


# --- start_add_item ---

@pytest.mark.asyncio
async def test_start_add_item_text_stores_pending_and_moves_to_awaiting_text(temp_equipment_db):
    query = FakeQuery("maint_admin_add:xray:common_failures:text", chat_id=111, message_id=555)
    context = _context()

    result = await mae.start_add_item(_callback_update(query), context)

    assert result == mae.AWAITING_TEXT
    assert context.user_data["maint_admin_pending"] == {
        "device": "xray", "item_key": "common_failures", "content_type": "text",
        "chat_id": 111, "message_id": 555,
    }
    assert "متن این آیتم" in query.edited_text


@pytest.mark.asyncio
async def test_start_add_item_photo_moves_to_awaiting_photo(temp_equipment_db):
    query = FakeQuery("maint_admin_add:xray:common_failures:photo")
    result = await mae.start_add_item(_callback_update(query), _context())
    assert result == mae.AWAITING_PHOTO


@pytest.mark.asyncio
async def test_start_add_item_video_moves_to_awaiting_video(temp_equipment_db):
    query = FakeQuery("maint_admin_add:xray:common_failures:video")
    result = await mae.start_add_item(_callback_update(query), _context())
    assert result == mae.AWAITING_VIDEO


@pytest.mark.asyncio
async def test_start_add_item_rejects_invalid_content_type(temp_equipment_db):
    query = FakeQuery("maint_admin_add:xray:common_failures:audio")
    result = await mae.start_add_item(_callback_update(query), _context())
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_start_add_item_rejects_invalid_item_key(temp_equipment_db):
    query = FakeQuery("maint_admin_add:xray:not_real:text")
    result = await mae.start_add_item(_callback_update(query), _context())
    assert result == ConversationHandler.END


# --- receive_text_item / receive_photo_item / receive_video_item ---

@pytest.mark.asyncio
async def test_receive_text_item_saves_and_confirms(temp_equipment_db, _log_action_mock):
    bot = FakeBot()
    context = _context(bot=bot, user_data={
        "maint_admin_pending": {"device": "xray", "item_key": "common_failures", "content_type": "text",
                                 "chat_id": 111, "message_id": 555},
    })
    update = _message_update(text="متن جدید آیتم")

    result = await mae.receive_text_item(update, context)

    assert result == mae.MENU
    items = await mr.get_items("xray", "common_failures")
    assert items == [("text", "متن جدید آیتم", None)]
    _log_action_mock.assert_awaited_once_with(42, "add_maintenance_item", target="xray:common_failures:text")
    assert "maint_admin_pending" not in context.user_data
    update.message.reply_text.assert_awaited_once_with("✅ ذخیره شد.")
    assert bot.edited_texts  # صفحه‌ی زیربخش دوباره رفرش شد
    assert bot.edited_texts[0][:2] == (111, 555)


@pytest.mark.asyncio
async def test_receive_photo_item_uses_largest_resolution_and_caption(temp_equipment_db):
    context = _context(user_data={
        "maint_admin_pending": {"device": "xray", "item_key": "spare_parts", "content_type": "photo",
                                 "chat_id": 111, "message_id": 555},
    })
    photos = [SimpleNamespace(file_id="small"), SimpleNamespace(file_id="large")]
    update = _message_update(photo=photos, caption="کپشن عکس")

    await mae.receive_photo_item(update, context)

    items = await mr.get_items("xray", "spare_parts")
    assert items == [("photo", "کپشن عکس", "large")]


@pytest.mark.asyncio
async def test_receive_video_item_saves_file_id_and_caption(temp_equipment_db):
    context = _context(user_data={
        "maint_admin_pending": {"device": "xray", "item_key": "spare_parts", "content_type": "video",
                                 "chat_id": 111, "message_id": 555},
    })
    update = _message_update(video=SimpleNamespace(file_id="vid123"), caption=None)

    await mae.receive_video_item(update, context)

    items = await mr.get_items("xray", "spare_parts")
    assert items == [("video", None, "vid123")]


@pytest.mark.asyncio
async def test_receive_text_item_without_pending_state_shows_internal_error(temp_equipment_db):
    context = _context(user_data={})
    update = _message_update(text="متن")

    result = await mae.receive_text_item(update, context)

    assert result == ConversationHandler.END
    update.message.reply_text.assert_awaited_once()
    assert "خطای داخلی" in update.message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_receive_text_item_still_succeeds_if_menu_refresh_fails(temp_equipment_db):
    class FailingBot(FakeBot):
        async def edit_message_text(self, chat_id, message_id, text, reply_markup=None):
            raise RuntimeError("simulated: message too old")

    context = _context(bot=FailingBot(), user_data={
        "maint_admin_pending": {"device": "xray", "item_key": "common_failures", "content_type": "text",
                                 "chat_id": 111, "message_id": 555},
    })
    update = _message_update(text="متن جدید")

    result = await mae.receive_text_item(update, context)

    assert result == mae.MENU
    items = await mr.get_items("xray", "common_failures")
    assert items  # ذخیره‌سازی موفق بود، فقط رفرش صفحه شکست خورد
    assert context.bot.sent_messages  # fallback به ارسال پیام تازه


# --- ask_clear_confirm / do_clear / cancel_clear ---

@pytest.mark.asyncio
async def test_ask_clear_confirm_shows_count_and_two_buttons(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "a", None)
    await mr.add_item("xray", "common_failures", "text", "b", None)
    query = FakeQuery("maint_admin_clear_ask:xray:common_failures")

    result = await mae.ask_clear_confirm(_callback_update(query), _context())

    assert result == mae.MENU
    assert "2 آیتم" in query.edited_text
    callback_datas = _flatten(query.edited_reply_markup)
    assert "maint_admin_clear_do:xray:common_failures" in callback_datas
    assert "maint_admin_clear_no:xray:common_failures" in callback_datas


@pytest.mark.asyncio
async def test_do_clear_removes_items_and_logs(temp_equipment_db, _log_action_mock):
    await mr.add_item("xray", "common_failures", "text", "a", None)
    query = FakeQuery("maint_admin_clear_do:xray:common_failures")

    result = await mae.do_clear(_callback_update(query), _context())

    assert result == mae.MENU
    assert await mr.get_items("xray", "common_failures") == []
    _log_action_mock.assert_awaited_once_with(42, "clear_maintenance_item", target="xray:common_failures")


@pytest.mark.asyncio
async def test_cancel_clear_leaves_items_untouched(temp_equipment_db):
    await mr.add_item("xray", "common_failures", "text", "a", None)
    query = FakeQuery("maint_admin_clear_no:xray:common_failures")

    result = await mae.cancel_clear(_callback_update(query), _context())

    assert result == mae.MENU
    assert await mr.get_items("xray", "common_failures") != []


# --- exit_to_device ---

@pytest.mark.asyncio
async def test_exit_to_device_ends_conversation_and_clears_pending(temp_equipment_db):
    query = FakeQuery("maint_admin_exit:xray")
    context = _context(user_data={"maint_admin_pending": {"device": "xray"}})

    result = await mae.exit_to_device(_callback_update(query), context)

    assert result == ConversationHandler.END
    assert "maint_admin_pending" not in context.user_data
    # ادمین باز هم دکمه‌ی مدیریت را روی صفحه‌ی دستگاه می‌بیند
    callback_datas = _flatten(query.edited_reply_markup)
    assert "maint_admin_open:xray" in callback_datas


@pytest.mark.asyncio
async def test_exit_to_device_rejects_fabricated_device(temp_equipment_db):
    query = FakeQuery("maint_admin_exit:not_real")
    result = await mae.exit_to_device(_callback_update(query), _context())
    assert result == ConversationHandler.END


# --- cancel + timeout ---

@pytest.mark.asyncio
async def test_cancel_clears_pending_state():
    context = _context(user_data={"maint_admin_pending": {"device": "xray"}})
    update = _message_update(text="/cancel")

    result = await mae.cancel(update, context)

    assert result == ConversationHandler.END
    assert "maint_admin_pending" not in context.user_data
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_timeout_clears_pending_and_notifies():
    bot = FakeBot()
    context = _context(bot=bot, user_data={"maint_admin_pending": {"device": "xray"}})
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=111))

    await mae.handle_timeout(update, context)

    assert "maint_admin_pending" not in context.user_data
    assert bot.sent_messages
    assert bot.sent_messages[0][0] == 111
