# tests/test_ephemeral.py

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils import ephemeral  # noqa: E402


def test_to_kwargs_shape():
    assert ephemeral.to_kwargs(4242) == {"receiver_user_id": 4242}


@pytest.mark.asyncio
async def test_send_or_fallback_uses_ephemeral_api_kwargs_when_it_succeeds():
    send_fn = AsyncMock()

    result = await ephemeral.send_or_fallback(send_fn, chat_id=555, user_id=4242, text="سلام")

    assert result is True
    send_fn.assert_awaited_once_with(chat_id=555, api_kwargs={"receiver_user_id": 4242}, text="سلام")


@pytest.mark.asyncio
async def test_send_or_fallback_falls_back_to_normal_visible_message_on_error():
    """رجوع به utils/ephemeral.py: هر خطای واقعی API (این قابلیت خیلی تازه‌ست)
    نباید جواب رو گم کنه — باید همون پیام رو بدون api_kwargs دوباره
    (این‌بار قابل‌دیدن برای کل چت) بفرسته."""
    send_fn = AsyncMock(side_effect=[Exception("ephemeral not supported here"), None])

    result = await ephemeral.send_or_fallback(send_fn, chat_id=555, user_id=4242, text="سلام")

    assert result is False
    assert send_fn.await_count == 2
    first_call, second_call = send_fn.await_args_list
    assert first_call.kwargs["api_kwargs"] == {"receiver_user_id": 4242}
    assert "api_kwargs" not in second_call.kwargs
    assert second_call.kwargs["chat_id"] == 555
    assert second_call.kwargs["text"] == "سلام"


@pytest.mark.asyncio
async def test_send_or_fallback_propagates_extra_kwargs_to_both_attempts():
    """مثلاً reply_parameters — باید هم توی تلاش ephemeral هم توی fallback
    باشه، نه فقط یکی‌شون."""
    send_fn = AsyncMock(side_effect=[Exception("boom"), None])

    await ephemeral.send_or_fallback(
        send_fn, chat_id=555, user_id=4242, text="سلام", reply_parameters="fake-reply-params",
    )

    for call in send_fn.await_args_list:
        assert call.kwargs["reply_parameters"] == "fake-reply-params"
