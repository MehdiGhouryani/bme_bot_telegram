# tests/test_ai_assistant_streaming.py
#
# پوشش سیم‌کشی stream_preview (utils/draft_stream.py) داخل ask_user_question —
# منطق خودِ streaming (تقسیم به گام، فرمول fallback و ...) در
# test_draft_stream.py تست شده؛ این‌جا فقط بررسی می‌کنیم که ask_command و
# handle_ai_callback نوع چت درست رو (خصوصی/گروهی) به ask_user_question
# پاس می‌دن، و این‌که پیام نهایی مستقل از نتیجه‌ی پیش‌نمایش همیشه ارسال
# می‌شه.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.constants import ChatType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import ai_usage_repository, feature_usage_repository  # noqa: E402
from bme_bot.handlers import ai_assistant  # noqa: E402
from bme_bot.services import ai_service  # noqa: E402
from bme_bot.utils import draft_stream  # noqa: E402


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", True)
    monkeypatch.setattr(draft_stream, "_STEP_DELAY_SECONDS", 0)
    monkeypatch.setattr(ai_usage_repository, "check_ai_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(ai_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(ai_usage_repository, "increment_ai_usage", AsyncMock())
    monkeypatch.setattr(feature_usage_repository, "log_usage", AsyncMock())
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("پاسخ کامل آزمایشی", "gemini/gemini-2.5-flash")))


def _fake_update_and_context(chat_type, question_text="سوال تست"):
    class FakeBot:
        def __init__(self):
            self.sent_messages = []
            self.do_api_request = AsyncMock(return_value=True)

        async def send_message(self, chat_id, text, **kwargs):
            self.sent_messages.append((chat_id, text))
            return SimpleNamespace(message_id=1)

        async def delete_message(self, chat_id, message_id):
            pass

    bot = FakeBot()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=555, type=chat_type),
        effective_user=SimpleNamespace(id=4242),
    )
    context = SimpleNamespace(bot=bot, args=question_text.split())
    return update, context, bot


@pytest.mark.asyncio
async def test_ask_command_in_private_chat_attempts_draft_streaming():
    update, context, bot = _fake_update_and_context(ChatType.PRIVATE)

    await ai_assistant.ask_command(update, context)

    bot.do_api_request.assert_awaited()
    first_call = bot.do_api_request.await_args_list[0]
    assert first_call.args[0] == "sendMessageDraft"


@pytest.mark.asyncio
async def test_ask_command_in_group_chat_never_attempts_draft_streaming():
    update, context, bot = _fake_update_and_context(ChatType.GROUP)

    await ai_assistant.ask_command(update, context)

    bot.do_api_request.assert_not_called()


@pytest.mark.asyncio
async def test_ask_command_final_message_sent_even_when_streaming_enabled():
    """پیام نهاییِ persist‌شده مستقل از پیش‌نمایشه — همیشه باید بره."""
    update, context, bot = _fake_update_and_context(ChatType.PRIVATE)

    await ai_assistant.ask_command(update, context)

    assert any("پاسخ کامل آزمایشی" in text for _, text in bot.sent_messages)


@pytest.mark.asyncio
async def test_ask_command_final_message_sent_even_when_draft_api_fails():
    update, context, bot = _fake_update_and_context(ChatType.PRIVATE)
    bot.do_api_request = AsyncMock(side_effect=Exception("TEXTDRAFT_PEER_INVALID"))

    await ai_assistant.ask_command(update, context)

    assert any("پاسخ کامل آزمایشی" in text for _, text in bot.sent_messages)


@pytest.mark.asyncio
async def test_ask_command_disabled_via_config_never_calls_draft_api(monkeypatch):
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", False)
    update, context, bot = _fake_update_and_context(ChatType.PRIVATE)

    await ai_assistant.ask_command(update, context)

    bot.do_api_request.assert_not_called()
    assert any("پاسخ کامل آزمایشی" in text for _, text in bot.sent_messages)


@pytest.mark.asyncio
async def test_ai_confirm_send_callback_in_private_chat_attempts_streaming():
    update, context, bot = _fake_update_and_context(ChatType.PRIVATE)
    context.user_data = {"ai_question_text": "سوال از دکمه"}
    query = SimpleNamespace(
        from_user=SimpleNamespace(id=4242),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        delete_message=AsyncMock(),
    )
    update.callback_query = query

    await ai_assistant.handle_ai_callback(update, context, "ai_confirm_send")

    bot.do_api_request.assert_awaited()


@pytest.mark.asyncio
async def test_ai_confirm_send_callback_in_group_chat_skips_streaming():
    update, context, bot = _fake_update_and_context(ChatType.GROUP)
    context.user_data = {"ai_question_text": "سوال از دکمه"}
    query = SimpleNamespace(
        from_user=SimpleNamespace(id=4242),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        delete_message=AsyncMock(),
    )
    update.callback_query = query

    await ai_assistant.handle_ai_callback(update, context, "ai_confirm_send")

    bot.do_api_request.assert_not_called()
