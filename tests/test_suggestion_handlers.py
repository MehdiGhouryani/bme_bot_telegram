# tests/test_suggestion_handlers.py
#
# suggestion.py قبلاً هیچ تست مستقلی نداشت. این فایل فقط handle_suggestion_message
# را پوشش می‌دهد — دقیقاً همان چیزی که اصلاح "@None" برای کاربر بدون
# نام‌کاربری را لمس کرد — نه کل فایل را.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.handlers import suggestion  # noqa: E402


def _make_update(username, full_name="کاربر تست", user_id=555, text="یه پیشنهاد خوب"):
    from_user = SimpleNamespace(id=user_id, username=username, full_name=full_name)
    message = SimpleNamespace(text=text, from_user=from_user, reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    return update, message


def _make_context():
    bot = SimpleNamespace(send_message=AsyncMock())
    return SimpleNamespace(bot=bot, user_data={})


@pytest.mark.asyncio
async def test_suggestion_with_username_included_in_admin_message(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", [111])
    update, message = _make_update(username="mmd_gholi")
    context = _make_context()

    await suggestion.handle_suggestion_message(update, context)

    sent_text = context.bot.send_message.await_args.kwargs["text"]
    assert "@mmd_gholi" in sent_text
    message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_suggestion_without_username_shows_dash_not_none(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", [111])
    update, message = _make_update(username=None)
    context = _make_context()

    await suggestion.handle_suggestion_message(update, context)

    sent_text = context.bot.send_message.await_args.kwargs["text"]
    assert "@None" not in sent_text
    assert "نام کاربری: —" in sent_text


@pytest.mark.asyncio
async def test_suggestion_resets_awaiting_flag_after_sending(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", [111])
    update, message = _make_update(username="x")
    context = _make_context()
    context.user_data["awaiting_request"] = True

    await suggestion.handle_suggestion_message(update, context)

    assert context.user_data["awaiting_request"] is False
