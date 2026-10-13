# tests/test_welcome_handlers.py

import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import settings_repository  # noqa: E402
from bme_bot.handlers import welcome  # noqa: E402


# ============================== ترigger در گروه ==============================

def _make_join_update(*, joined_ids_and_names, chat_id=-100999):
    members = [SimpleNamespace(id=uid, first_name=name) for uid, name in joined_ids_and_names]
    message = SimpleNamespace(new_chat_members=members)
    update = SimpleNamespace(message=message, effective_chat=SimpleNamespace(id=chat_id))
    bot = SimpleNamespace(id=1, send_message=AsyncMock())
    context = SimpleNamespace(bot=bot)
    return update, context, bot


@pytest.mark.asyncio
async def test_no_welcome_sent_when_disabled(monkeypatch):
    monkeypatch.setattr(welcome, "is_welcome_enabled", AsyncMock(return_value=False))
    send_mock = AsyncMock()
    monkeypatch.setattr(welcome, "send_rich_message", send_mock)
    update, context, bot = _make_join_update(joined_ids_and_names=[(4242, "علی")])

    await welcome.handle_new_chat_members(update, context)

    send_mock.assert_not_called()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_welcome_substitutes_name_and_uses_rich_message(monkeypatch):
    monkeypatch.setattr(welcome, "is_welcome_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(welcome, "get_welcome_text", AsyncMock(return_value="سلام {name} عزیز"))
    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(welcome, "send_rich_message", send_mock)
    update, context, bot = _make_join_update(joined_ids_and_names=[(4242, "علی")])

    await welcome.handle_new_chat_members(update, context)

    send_mock.assert_awaited_once_with(bot, -100999, "سلام علی عزیز")
    bot.send_message.assert_not_called()  # چون rich موفق بود، نیازی به fallback نبود


@pytest.mark.asyncio
async def test_welcome_escapes_markdown_injection_in_joining_user_name(monkeypatch):
    """امنیتی: اسم تلگرام کاملاً دست خودِ کاربره. بدون escape، اسمی مثل
    "[کلیک کنید](https://evil.com)" یه لینک قلابی توی پیام رسمی خوشامدگویی
    بات می‌ساخت — رجوع به کامنت بالای _escape_untrusted_name."""
    monkeypatch.setattr(welcome, "is_welcome_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(welcome, "get_welcome_text", AsyncMock(return_value="سلام {name}"))
    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(welcome, "send_rich_message", send_mock)
    malicious_name = "[کلیک کنید](https://evil.com)"
    update, context, bot = _make_join_update(joined_ids_and_names=[(4242, malicious_name)])

    await welcome.handle_new_chat_members(update, context)

    sent_text = send_mock.call_args.args[2]
    assert "](https://evil.com)" not in sent_text  # سینتکس لینک خنثی شده
    assert "\\[کلیک کنید\\]\\(https://evil.com\\)" in sent_text


def test_escape_untrusted_name_handles_pre_existing_backslash():
    """باگ ظریفی که در یه بازبینی پیدا شد: اگه اول خودِ بک‌اسلش رو escape
    نکنیم، یه اسم با بک‌اسلشِ از قبل موجود (مثلاً "\\\\[لینک](...)") می‌تونه
    escape ما رو خنثی کنه — "\\\\" + "\\\\[" (escapeِ خودمون) با هم می‌شن
    "\\\\\\\\[" یعنی یه بک‌اسلشِ escape‌شده + یه "[" کاملاً بی‌escape دوباره.
    رجوع به کامنت داخل _escape_untrusted_name."""
    adversarial = "\\" + "[کلیک کنید](https://evil.com)"

    escaped = welcome._escape_untrusted_name(adversarial)

    assert re.search(r"(?<!\\)\[", escaped) is None  # هیچ "[" بدون بک‌اسلش بلافاصله قبلش نمونده
    assert re.search(r"(?<!\\)\(", escaped) is None


@pytest.mark.asyncio
async def test_welcome_falls_back_to_plain_message_when_rich_fails(monkeypatch):
    monkeypatch.setattr(welcome, "is_welcome_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(welcome, "get_welcome_text", AsyncMock(return_value="سلام {name}"))
    monkeypatch.setattr(welcome, "send_rich_message", AsyncMock(return_value=False))
    update, context, bot = _make_join_update(joined_ids_and_names=[(4242, "علی")])

    await welcome.handle_new_chat_members(update, context)

    bot.send_message.assert_awaited_once_with(chat_id=-100999, text="سلام علی")


@pytest.mark.asyncio
async def test_welcome_skips_the_bot_itself_and_uses_fallback_name_when_missing(monkeypatch):
    """رجوع به کامنت داخل handle_new_chat_members: خودِ بات هم یه بار
    «عضو جدید» گروهه (وقتی اولین‌بار اضافه می‌شه) — نباید به خودش خوشامد
    بگیم. کاربر بدون first_name (نادر ولی ممکن) نباید کرش کنه."""
    monkeypatch.setattr(welcome, "is_welcome_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(welcome, "get_welcome_text", AsyncMock(return_value="سلام {name}"))
    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(welcome, "send_rich_message", send_mock)
    update, context, bot = _make_join_update(
        joined_ids_and_names=[(1, "خودِ بات"), (4242, None)],  # id=1 با bot.id در _make_join_update یکیه
    )

    await welcome.handle_new_chat_members(update, context)

    send_mock.assert_awaited_once_with(bot, -100999, "سلام دوست عزیز")


# ============================== پنل ادمین: toggle ==============================

def _make_settings_callback_update(user_id=42):
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=user_id))
    return update, query


@pytest.mark.asyncio
async def test_non_admin_cannot_toggle_settings(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])  # ۴۲ ادمین نیست
    update, query = _make_settings_callback_update(user_id=42)
    context = SimpleNamespace()

    await welcome.handle_settings_toggle(update, context)

    query.edit_message_text.assert_not_called()
    query.answer.assert_awaited_once()
    assert query.answer.call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_toggle_flips_current_value_and_refreshes_menu(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])
    monkeypatch.setattr(welcome, "is_welcome_enabled", AsyncMock(return_value=True))
    set_mock = AsyncMock()
    monkeypatch.setattr(settings_repository, "set_bool_setting", set_mock)
    update, query = _make_settings_callback_update(user_id=42)
    context = SimpleNamespace()

    await welcome.handle_settings_toggle(update, context)

    set_mock.assert_awaited_once_with(welcome.WELCOME_ENABLED_KEY, False)
    assert "❌ غیرفعال" in query.edit_message_text.call_args.args[0]


# ============================== پنل ادمین: ویرایش متن ==============================

class FakeBot:
    """rich_side_effect: اگه Exception باشه، do_api_request همونو raise
    می‌کنه — پیش‌فرض None یعنی موفق. عیناً همون الگوی FakeBot در
    test_equipment_admin_edit.py."""

    def __init__(self, rich_side_effect=None):
        self.rich_calls = []
        self._rich_side_effect = rich_side_effect

        async def _do_api_request(method, payload):
            self.rich_calls.append((method, payload))
            if isinstance(self._rich_side_effect, Exception):
                raise self._rich_side_effect
            return {"ok": True}

        self.do_api_request = AsyncMock(side_effect=_do_api_request)


def _make_text_message_update(text, chat_id=42):
    message = SimpleNamespace(text=text, entities=[], reply_text=AsyncMock())
    update = SimpleNamespace(message=message, effective_chat=SimpleNamespace(id=chat_id))
    return update, message


@pytest.mark.asyncio
async def test_receive_welcome_text_rejects_invalid_markdown_without_saving():
    bot = FakeBot(rich_side_effect=BadRequest("Can't parse entities"))
    update, message = _make_text_message_update("**نیمه‌کاره")
    context = SimpleNamespace(bot=bot, user_data={})

    result = await welcome.receive_welcome_text(update, context)

    assert result == welcome.AWAITING_TEXT
    assert "pending_welcome_text" not in context.user_data
    assert bot.rich_calls  # تلاش پیش‌نمایش انجام شد، ولی رد شد


@pytest.mark.asyncio
async def test_receive_welcome_text_shows_preview_and_awaits_confirmation():
    bot = FakeBot()
    update, message = _make_text_message_update("سلام {name} عزیز")
    context = SimpleNamespace(bot=bot, user_data={})

    result = await welcome.receive_welcome_text(update, context)

    assert result == welcome.AWAITING_CONFIRMATION
    assert context.user_data["pending_welcome_text"] == "سلام {name} عزیز"
    # پیش‌نمایش باید با اسم نمونه (نه {name} خام) به تلگرام فرستاده شده باشه.
    _, payload = bot.rich_calls[0]
    assert welcome._SAMPLE_NAME_FOR_PREVIEW in payload["rich_message"]["markdown"]
    assert "{name}" not in payload["rich_message"]["markdown"]


@pytest.mark.asyncio
async def test_confirm_welcome_text_edit_saves_and_ends_conversation(monkeypatch):
    from telegram.ext import ConversationHandler

    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={"pending_welcome_text": "متن نهایی"})
    set_mock = AsyncMock()
    monkeypatch.setattr(settings_repository, "set_setting", set_mock)

    result = await welcome.confirm_welcome_text_edit(update, context)

    assert result == ConversationHandler.END
    set_mock.assert_awaited_once_with(welcome.WELCOME_TEXT_KEY, "متن نهایی")
    assert "pending_welcome_text" not in context.user_data


@pytest.mark.asyncio
async def test_confirm_welcome_text_edit_without_pending_text_is_rejected_defensively():
    from telegram.ext import ConversationHandler

    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={})

    result = await welcome.confirm_welcome_text_edit(update, context)

    assert result == ConversationHandler.END
    assert "خطای داخلی" in query.edit_message_text.call_args.args[0]
