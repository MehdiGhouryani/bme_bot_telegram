# tests/test_equipment_admin_edit.py
#
# تست‌های ConversationHandler دکمه‌ی ✏️
# ویرایش ادمین روی اطلاعات دستگاه — اعتبارسنجی، مسیر موفق (شامل هر دو شاخه‌ی
# متن/عکس)، لاگ اقدام ادمین، و timeout.

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest
from telegram.ext import ConversationHandler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config, equipment_tree  # noqa: E402
from bme_bot.db import admin_actions_repository, equipment_repository  # noqa: E402
from bme_bot.handlers import equipment_admin_edit  # noqa: E402


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
        ("xray", "تعریف اشعه ایکس", "PHOTO123", "انواع", "ساختار قدیمی", "عملکرد", "تک مشابه", "مزایا", "ایمنی"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "EQUIPMENT_DB_PATH", str(db_path))
    return db_path


class FakeQuery:
    def __init__(self, data, chat_id=111, message_id=555):
        self.data = data
        self.answers = []
        self.message = SimpleNamespace(chat_id=chat_id, message_id=message_id)

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))


class FakeBot:
    def __init__(self, fail_edit=False):
        self.fail_edit = fail_edit
        self.sent_messages = []
        self.edited_texts = []
        self.edited_captions = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent_messages.append((chat_id, text))

    async def edit_message_text(self, chat_id, message_id, text, reply_markup=None):
        if self.fail_edit:
            raise RuntimeError("simulated: message too old to edit")
        self.edited_texts.append((chat_id, message_id, text, reply_markup))

    async def edit_message_caption(self, chat_id, message_id, caption, reply_markup=None):
        if self.fail_edit:
            raise RuntimeError("simulated: message too old to edit")
        self.edited_captions.append((chat_id, message_id, caption, reply_markup))


def _make_callback_update(query, user_id=42):
    return SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=user_id))


def _make_message_update(text, user_id=42, chat_id=111):
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(message=message, effective_user=SimpleNamespace(id=user_id), effective_chat=SimpleNamespace(id=chat_id))


def _make_context(bot=None, user_data=None):
    return SimpleNamespace(bot=bot or FakeBot(), user_data=user_data if user_data is not None else {})


# --- start_edit: اعتبارسنجی ---

@pytest.mark.asyncio
async def test_non_admin_cannot_start_edit(temp_equipment_db, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])  # ۴۲ ادمین نیست
    query = FakeQuery("admin_edit_field:xray:structure:imaging_devices")
    update = _make_callback_update(query, user_id=42)
    context = _make_context()

    result = await equipment_admin_edit.start_edit(update, context)

    assert result == ConversationHandler.END
    assert query.answers and query.answers[0][1] is True  # show_alert
    assert "equipment_edit" not in context.user_data


@pytest.mark.asyncio
async def test_malformed_callback_data_is_rejected(temp_equipment_db, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])
    query = FakeQuery("admin_edit_field:xray:structure")  # فقط ۳ تکه، نه ۴
    update = _make_callback_update(query)
    context = _make_context()

    result = await equipment_admin_edit.start_edit(update, context)

    assert result == ConversationHandler.END
    assert query.answers and "نامعتبر" in query.answers[0][0]


@pytest.mark.asyncio
async def test_fabricated_device_is_rejected(temp_equipment_db, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])
    query = FakeQuery("admin_edit_field:fake_device:structure:imaging_devices")
    update = _make_callback_update(query)
    context = _make_context()

    result = await equipment_admin_edit.start_edit(update, context)

    assert result == ConversationHandler.END
    assert query.answers and "یافت نشد" in query.answers[0][0]


@pytest.mark.asyncio
async def test_unlisted_action_is_rejected(temp_equipment_db, monkeypatch):
    """همان allow-list که equipment_repository برای SQL امن‌سازی استفاده
    می‌کند، اینجا هم قبل از شروع مکالمه چک می‌شود."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])
    query = FakeQuery("admin_edit_field:xray:secret_column:imaging_devices")
    update = _make_callback_update(query)
    context = _make_context()

    result = await equipment_admin_edit.start_edit(update, context)

    assert result == ConversationHandler.END
    assert query.answers and "یافت نشد" in query.answers[0][0]


@pytest.mark.asyncio
async def test_valid_edit_request_prompts_and_stores_state(temp_equipment_db, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])
    query = FakeQuery("admin_edit_field:xray:structure:imaging_devices", chat_id=111, message_id=555)
    bot = FakeBot()
    update = _make_callback_update(query)
    context = _make_context(bot=bot)

    result = await equipment_admin_edit.start_edit(update, context)

    assert result == equipment_admin_edit.AWAITING_NEW_TEXT
    assert context.user_data["equipment_edit"] == {
        "device": "xray", "action": "structure", "line": "imaging_devices",
        "chat_id": 111, "message_id": 555,
    }
    assert bot.sent_messages
    assert "ساختار قدیمی" in bot.sent_messages[0][1]


@pytest.mark.asyncio
async def test_receive_new_text_rejects_invalid_markdown_without_saving(temp_equipment_db, monkeypatch):
    """رگرسیون: اگه متن ادمین فرمت مارک‌داون معتبری نداشته باشه (مثلاً یه
    `*` بدون جفت)، equipment_callbacks بعداً با parse_mode=MARKDOWN می‌خواد
    نشونش بده و شکست می‌خوره — چیزی که قبلاً هیچ‌جا چک نمی‌شد و کل بخش رو
    برای همه‌ی کاربران خراب می‌کرد. الان باید همون‌جا رد بشه، هیچی هم
    ذخیره نشه."""
    log_action_mock = AsyncMock()
    monkeypatch.setattr(admin_actions_repository, "log_action", log_action_mock)
    bot = FakeBot()
    context = _make_context(bot=bot, user_data={
        "equipment_edit": {"device": "xray", "action": "structure", "line": "imaging_devices",
                            "chat_id": 111, "message_id": 555},
    })
    update = _make_message_update("متن با ستاره‌ی * تک و بدون جفت")
    update.message.reply_text = AsyncMock(side_effect=[BadRequest("Can't parse entities"), None])

    result = await equipment_admin_edit.receive_new_text(update, context)

    assert result == equipment_admin_edit.AWAITING_NEW_TEXT
    stored = await equipment_repository.get_action_text("xray", "structure")
    assert stored != "متن با ستاره‌ی * تک و بدون جفت"
    log_action_mock.assert_not_called()
    assert not bot.edited_texts
    # پیام دوم (توضیح خطا برای ادمین) باید واقعاً رفته باشه
    assert update.message.reply_text.await_count == 2


# --- receive_new_text: مسیر موفق ---

@pytest.mark.asyncio
async def test_receive_new_text_saves_logs_and_confirms(temp_equipment_db, monkeypatch):
    log_action_mock = AsyncMock()
    monkeypatch.setattr(admin_actions_repository, "log_action", log_action_mock)
    bot = FakeBot()
    context = _make_context(bot=bot, user_data={
        "equipment_edit": {"device": "xray", "action": "structure", "line": "imaging_devices",
                            "chat_id": 111, "message_id": 555},
    })
    update = _make_message_update("ساختار تازه و به‌روز")

    result = await equipment_admin_edit.receive_new_text(update, context)

    assert result == ConversationHandler.END
    stored = await equipment_repository.get_action_text("xray", "structure")
    assert stored == "ساختار تازه و به‌روز"
    log_action_mock.assert_awaited_once_with(42, "edit_equipment_field", target="xray:structure")
    assert "equipment_edit" not in context.user_data
    update.message.reply_text.assert_awaited_once()
    sent_text, sent_kwargs = update.message.reply_text.await_args.args[0], update.message.reply_text.await_args.kwargs
    assert "ساختار تازه و به‌روز" in sent_text  # پیش‌نمایش شامل خودِ متن ذخیره‌شده است
    assert sent_kwargs.get("parse_mode") is not None  # با همون parse_mode واقعی چک شده
    # پیام اصلی (همانی که ادمین رویش ✏️ زده بود) هم باید زنده‌سازی شده باشد
    assert bot.edited_texts
    chat_id, message_id, text, _ = bot.edited_texts[0]
    assert (chat_id, message_id, text) == (111, 555, "ساختار تازه و به‌روز")


@pytest.mark.asyncio
async def test_receive_new_text_for_definition_edits_caption_not_text(temp_equipment_db, monkeypatch):
    """پوشش مسیر عکس الزامی بود: definition باید edit_message_caption صدا
    بزند، نه edit_message_text (که روی پیام‌های عکس‌دار خطا می‌دهد)."""
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())
    bot = FakeBot()
    context = _make_context(bot=bot, user_data={
        "equipment_edit": {"device": "xray", "action": "definition", "line": "imaging_devices",
                            "chat_id": 111, "message_id": 555},
    })
    update = _make_message_update("تعریف تازه")

    await equipment_admin_edit.receive_new_text(update, context)

    assert not bot.edited_texts
    assert bot.edited_captions
    chat_id, message_id, caption, _ = bot.edited_captions[0]
    assert (chat_id, message_id, caption) == (111, 555, "تعریف تازه")


@pytest.mark.asyncio
async def test_receive_new_text_rejects_definition_over_limit_in_utf16_units_even_if_under_in_python_len(
    temp_equipment_db, monkeypatch,
):
    """۱۰۲۰ کاراکتر فارسی (۱ واحد UTF-16 هرکدام) + ۳ تا 👤 (۲ واحد UTF-16
    هرکدام، خارج از BMP) = len() پایتون ۱۰۲۳ (زیر سقف ۱۰۲۴!) ولی UTF-16
    واقعی ۱۰۲۶ (بالای سقف). اگه چک با len() خام انجام می‌شد (باگی که
    همین تست جلوش رو می‌گیره)، این متن اشتباهاً قبول می‌شد."""
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())
    bot = FakeBot()
    text_with_emoji = "ا" * 1020 + "👤" * 3
    assert len(text_with_emoji) == 1023  # زیر سقف از نظر len() خام پایتون
    context = _make_context(bot=bot, user_data={
        "equipment_edit": {"device": "xray", "action": "definition", "line": "imaging_devices",
                            "chat_id": 111, "message_id": 555},
    })
    update = _make_message_update(text_with_emoji)

    result = await equipment_admin_edit.receive_new_text(update, context)

    assert result == equipment_admin_edit.AWAITING_NEW_TEXT
    stored = await equipment_repository.get_action_text("xray", "definition")
    assert stored != text_with_emoji


@pytest.mark.asyncio
async def test_receive_new_text_rejects_oversized_definition(temp_equipment_db, monkeypatch):
    """definition به‌شکل کپشن عکس نمایش داده می‌شود (سقف تلگرام ۱۰۲۴ کاراکتر)
    — یه متن طولانی‌تر باید رد بشه، نه این‌که «موفق» ذخیره بشه و بعداً همه‌ی
    کاربران رو خراب کنه."""
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())
    bot = FakeBot()
    oversized_text = "الف" * 1025
    context = _make_context(bot=bot, user_data={
        "equipment_edit": {"device": "xray", "action": "definition", "line": "imaging_devices",
                            "chat_id": 111, "message_id": 555},
    })
    update = _make_message_update(oversized_text)

    result = await equipment_admin_edit.receive_new_text(update, context)

    assert result == equipment_admin_edit.AWAITING_NEW_TEXT
    stored = await equipment_repository.get_action_text("xray", "definition")
    assert stored != oversized_text  # چیزی ذخیره نشده
    assert not bot.edited_captions
    admin_actions_repository.log_action.assert_not_called()
    warning_text = update.message.reply_text.await_args.args[0]
    assert "1024" in warning_text


@pytest.mark.asyncio
async def test_receive_new_text_allows_oversized_text_for_non_definition_action(temp_equipment_db, monkeypatch):
    """محدودیت فقط مخصوص definition است — بقیه‌ی اکشن‌ها با edit_message_text
    نمایش داده می‌شوند (سقف ۴۰۹۶)، پس نباید به این سقف ۱۰۲۴ محدود بشن."""
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())
    bot = FakeBot()
    long_but_allowed_text = "ب" * 1500
    context = _make_context(bot=bot, user_data={
        "equipment_edit": {"device": "xray", "action": "structure", "line": "imaging_devices",
                            "chat_id": 111, "message_id": 555},
    })
    update = _make_message_update(long_but_allowed_text)

    result = await equipment_admin_edit.receive_new_text(update, context)

    assert result == ConversationHandler.END
    stored = await equipment_repository.get_action_text("xray", "structure")
    assert stored == long_but_allowed_text


@pytest.mark.asyncio
async def test_receive_new_text_still_succeeds_if_original_message_refresh_fails(temp_equipment_db, monkeypatch):
    """اگر پیام اصلی خیلی قدیمی/غیرقابل‌ویرایش باشد، ذخیره‌سازی همچنان باید
    موفق بماند — فقط منظره‌ی زنده‌سازی نمی‌شود، کل عملیات نباید شکست بخورد."""
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())
    bot = FakeBot(fail_edit=True)
    context = _make_context(bot=bot, user_data={
        "equipment_edit": {"device": "xray", "action": "structure", "line": "imaging_devices",
                            "chat_id": 111, "message_id": 555},
    })
    update = _make_message_update("ساختار تازه")

    result = await equipment_admin_edit.receive_new_text(update, context)

    assert result == ConversationHandler.END
    stored = await equipment_repository.get_action_text("xray", "structure")
    assert stored == "ساختار تازه"
    update.message.reply_text.assert_awaited_once()  # تاییدیه همچنان رفته


@pytest.mark.asyncio
async def test_receive_new_text_without_state_shows_internal_error(temp_equipment_db):
    """محافظ دفاعی: اگر state گم شده باشد (نباید عملاً پیش بیاید)."""
    context = _make_context(user_data={})
    update = _make_message_update("یک متنی")

    result = await equipment_admin_edit.receive_new_text(update, context)

    assert result == ConversationHandler.END
    update.message.reply_text.assert_awaited_once()


# --- cancel + timeout ---

@pytest.mark.asyncio
async def test_cancel_edit_clears_state():
    context = _make_context(user_data={"equipment_edit": {"device": "xray"}})
    update = _make_message_update("/cancel")

    result = await equipment_admin_edit.cancel_edit(update, context)

    assert result == ConversationHandler.END
    assert "equipment_edit" not in context.user_data
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_edit_timeout_clears_state_and_notifies():
    bot = SimpleNamespace(send_message=AsyncMock())
    context = _make_context(bot=bot, user_data={"equipment_edit": {"device": "xray"}})
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=111))

    await equipment_admin_edit.handle_edit_timeout(update, context)

    assert "equipment_edit" not in context.user_data
    bot.send_message.assert_awaited_once()
    assert bot.send_message.await_args.kwargs["chat_id"] == 111
