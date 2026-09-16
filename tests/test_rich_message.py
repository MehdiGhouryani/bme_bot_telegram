# tests/test_rich_message.py

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest, NetworkError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils import rich_message  # noqa: E402


class FakeBot:
    def __init__(self, side_effect=None):
        self.do_api_request = AsyncMock(side_effect=side_effect)


@pytest.mark.asyncio
async def test_send_rich_message_success_calls_correct_endpoint_and_shape():
    bot = FakeBot()

    result = await rich_message.send_rich_message(bot, 123, "# عنوان\nمتن جزوه")

    assert result is True
    bot.do_api_request.assert_awaited_once_with(
        "sendRichMessage",
        {"chat_id": 123, "rich_message": {"markdown": "# عنوان\nمتن جزوه"}},
    )


@pytest.mark.asyncio
async def test_send_rich_message_passes_extra_top_level_kwargs():
    bot = FakeBot()

    await rich_message.send_rich_message(bot, 123, "متن", reply_parameters={"message_id": 5})

    _, kwargs_payload = bot.do_api_request.await_args.args
    assert kwargs_payload["reply_parameters"] == {"message_id": 5}
    assert kwargs_payload["rich_message"] == {"markdown": "متن"}


@pytest.mark.asyncio
async def test_send_rich_message_returns_false_on_telegram_error_not_raises():
    bot = FakeBot(side_effect=BadRequest("rich message blocks too long"))

    result = await rich_message.send_rich_message(bot, 123, "متن")

    assert result is False


@pytest.mark.asyncio
async def test_send_rich_message_retries_transient_network_error_then_succeeds():
    bot = FakeBot(side_effect=[NetworkError("timeout"), None])

    result = await rich_message.send_rich_message(bot, 123, "متن")

    assert result is True
    assert bot.do_api_request.await_count == 2


@pytest.mark.asyncio
async def test_send_rich_message_skips_oversized_content_without_calling_api():
    bot = FakeBot()
    oversized = "الف" * (rich_message.RICH_MESSAGE_MAX_BYTES + 10)

    result = await rich_message.send_rich_message(bot, 123, oversized)

    assert result is False
    bot.do_api_request.assert_not_called()


# --- edit_rich_message ---

@pytest.mark.asyncio
async def test_edit_rich_message_success_calls_edit_message_text_with_rich_message():
    """editMessageText (نه یه متد جدا) — چون Bot API 10.1 پارامتر
    rich_message رو مستقیم به همین متد اضافه کرده، نه یه متد ادیت جدا."""
    bot = FakeBot()

    result = await rich_message.edit_rich_message(bot, 123, 555, "## عنوان\nمتن")

    assert result is True
    bot.do_api_request.assert_awaited_once_with(
        "editMessageText",
        {"chat_id": 123, "message_id": 555, "rich_message": {"markdown": "## عنوان\nمتن"}},
    )


@pytest.mark.asyncio
async def test_edit_rich_message_includes_reply_markup_when_given():
    bot = FakeBot()
    markup = {"inline_keyboard": [[{"text": "ok", "callback_data": "x"}]]}

    await rich_message.edit_rich_message(bot, 123, 555, "متن", reply_markup=markup)

    _, kwargs_payload = bot.do_api_request.await_args.args
    assert kwargs_payload["reply_markup"] == markup


@pytest.mark.asyncio
async def test_edit_rich_message_omits_reply_markup_when_not_given():
    bot = FakeBot()

    await rich_message.edit_rich_message(bot, 123, 555, "متن")

    _, kwargs_payload = bot.do_api_request.await_args.args
    assert "reply_markup" not in kwargs_payload


@pytest.mark.asyncio
async def test_edit_rich_message_returns_false_on_telegram_error_not_raises():
    bot = FakeBot(side_effect=BadRequest("message is not modified or too old to edit"))

    result = await rich_message.edit_rich_message(bot, 123, 555, "متن")

    assert result is False


@pytest.mark.asyncio
async def test_edit_rich_message_retries_transient_network_error_then_succeeds():
    bot = FakeBot(side_effect=[NetworkError("timeout"), None])

    result = await rich_message.edit_rich_message(bot, 123, 555, "متن")

    assert result is True
    assert bot.do_api_request.await_count == 2


@pytest.mark.asyncio
async def test_edit_rich_message_skips_oversized_content_without_calling_api():
    bot = FakeBot()
    oversized = "الف" * (rich_message.RICH_MESSAGE_MAX_BYTES + 10)

    result = await rich_message.edit_rich_message(bot, 123, 555, oversized)

    assert result is False
    bot.do_api_request.assert_not_called()


@pytest.mark.asyncio
async def test_edit_rich_message_returns_false_when_bot_lacks_do_api_request():
    """سازگاری با bot object هایی که هنوز این متد رو ندارن (مثلاً نسخه‌های
    قدیمی‌تر PTB/تست‌های سبک‌وزن) — باید بی‌صدا False برگردونه، نه کرش کنه."""
    class MinimalBot:
        pass

    result = await rich_message.edit_rich_message(MinimalBot(), 123, 555, "متن")

    assert result is False
