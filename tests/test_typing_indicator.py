# tests/test_typing_indicator.py

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils import typing_indicator  # noqa: E402


@pytest.mark.asyncio
async def test_send_typing_calls_send_chat_action_with_typing():
    bot = AsyncMock()

    await typing_indicator.send_typing(bot, 555)

    bot.send_chat_action.assert_awaited_once_with(chat_id=555, action="typing")


@pytest.mark.asyncio
async def test_send_typing_swallows_errors_without_raising():
    bot = AsyncMock()
    bot.send_chat_action.side_effect = Exception("network blip")

    await typing_indicator.send_typing(bot, 555)  # نباید exception بیرون بزنه
