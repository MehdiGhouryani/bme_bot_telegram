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
