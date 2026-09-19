# tests/test_draft_stream.py

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.utils import draft_stream  # noqa: E402


class FakeBot:
    def __init__(self, side_effect=None):
        self.do_api_request = AsyncMock(side_effect=side_effect)


# --------------------------- _reveal_steps ---------------------------

def test_reveal_steps_short_text_single_step():
    assert draft_stream._reveal_steps("سلام") == ["سلام"]


def test_reveal_steps_empty_text_no_steps():
    assert draft_stream._reveal_steps("") == []


def test_reveal_steps_are_growing_prefixes_ending_at_full_text():
    text = "الف" * 200
    steps = draft_stream._reveal_steps(text)

    assert len(steps) > 1
    assert steps[-1] == text
    for a, b in zip(steps, steps[1:]):
        assert b.startswith(a)
        assert len(b) > len(a)


def test_reveal_steps_caps_at_max_draft_chars():
    text = "x" * 10000
    steps = draft_stream._reveal_steps(text)
    assert len(steps[-1]) == draft_stream._MAX_DRAFT_CHARS


# --------------------------- stream_preview ---------------------------

@pytest.mark.asyncio
async def test_stream_preview_returns_false_for_group_chat(monkeypatch):
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", True)
    bot = FakeBot()

    result = await draft_stream.stream_preview(bot, 123, "متن پاسخ", is_private_chat=False)

    assert result is False
    bot.do_api_request.assert_not_called()


@pytest.mark.asyncio
async def test_stream_preview_returns_false_when_disabled_via_config(monkeypatch):
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", False)
    bot = FakeBot()

    result = await draft_stream.stream_preview(bot, 123, "متن پاسخ", is_private_chat=True)

    assert result is False
    bot.do_api_request.assert_not_called()


@pytest.mark.asyncio
async def test_stream_preview_success_calls_draft_endpoint_with_growing_text(monkeypatch):
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", True)
    monkeypatch.setattr(draft_stream, "_STEP_DELAY_SECONDS", 0)  # سرعت تست
    bot = FakeBot()
    text = "الف" * 200

    result = await draft_stream.stream_preview(bot, 123, text, is_private_chat=True)

    assert result is True
    assert bot.do_api_request.await_count == len(draft_stream._reveal_steps(text))
    first_call = bot.do_api_request.await_args_list[0]
    assert first_call.args[0] == "sendRichMessageDraft"
    assert first_call.args[1]["chat_id"] == 123
    assert first_call.args[1]["draft_id"] == draft_stream._DRAFT_ID
    last_call = bot.do_api_request.await_args_list[-1]
    assert last_call.args[1]["rich_message"]["markdown"] == text


@pytest.mark.asyncio
async def test_stream_preview_wraps_partial_text_as_rich_message_markdown(monkeypatch):
    """رجوع به تغییر بند ۴: دیگه plain-text نیستیم — پیلود باید دقیقاً هم‌شکل
    rich_message.send_rich_message باشه (کلید rich_message.markdown)، نه
    text خام قدیمی."""
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", True)
    monkeypatch.setattr(draft_stream, "_STEP_DELAY_SECONDS", 0)
    bot = FakeBot()

    await draft_stream.stream_preview(bot, 123, "**نیمه‌کاره", is_private_chat=True)

    call_payload = bot.do_api_request.await_args_list[0].args[1]
    assert call_payload["rich_message"] == {"markdown": "**نیمه‌کاره"}
    assert "text" not in call_payload


@pytest.mark.asyncio
async def test_stream_preview_falls_back_silently_on_api_error_mid_stream(monkeypatch):
    """مثلاً چت گروهی که is_private_chat اشتباه True داده شده، یا هر خطای
    واقعی API — حتی وسط استریم، نه فقط گام اول."""
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", True)
    monkeypatch.setattr(draft_stream, "_STEP_DELAY_SECONDS", 0)
    bot = FakeBot(side_effect=[None, Exception("TEXTDRAFT_PEER_INVALID")])

    result = await draft_stream.stream_preview(bot, 123, "الف" * 200, is_private_chat=True)

    assert result is False


@pytest.mark.asyncio
async def test_stream_preview_falls_back_on_unexpected_error_not_just_telegram_error(monkeypatch):
    """حتی خطای کاملاً غیرمنتظره (نه لزوماً TelegramError) نباید کل جریان
    /ask رو بشکنه — این یه قابلیت کاملاً افزوده و best-effort است."""
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", True)
    bot = FakeBot(side_effect=AttributeError("something unexpected"))

    result = await draft_stream.stream_preview(bot, 123, "متن", is_private_chat=True)

    assert result is False
