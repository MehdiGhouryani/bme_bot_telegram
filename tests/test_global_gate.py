# tests/test_global_gate.py
#
# تست دروازه‌ی سراسری — پوشش «بن ناقص» (membership_required فقط دو
# دیسپچر اصلی را می‌پوشاند، نه /ask، /ai، /start، یا هندلر عکس OCR).

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.db import users_repository  # noqa: E402
from bme_bot.handlers import global_gate  # noqa: E402
from telegram.ext import ApplicationHandlerStop  # noqa: E402


@pytest.mark.asyncio
async def test_banned_user_raises_application_handler_stop(monkeypatch):
    monkeypatch.setattr(users_repository, "is_banned", AsyncMock(return_value=True))
    touch_mock = AsyncMock()
    monkeypatch.setattr(users_repository, "touch_last_seen", touch_mock)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        callback_query=None,
        effective_chat=SimpleNamespace(id=42),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    with pytest.raises(ApplicationHandlerStop):
        await global_gate.enforce_ban_and_track_activity(update, context)

    context.bot.send_message.assert_awaited_once_with(chat_id=42, text=global_gate._BANNED_MESSAGE)
    touch_mock.assert_not_called()  # کاربر بن‌شده لازم نیست last_seen بگیرد


@pytest.mark.asyncio
async def test_banned_user_via_callback_query_gets_alert_not_send_message(monkeypatch):
    monkeypatch.setattr(users_repository, "is_banned", AsyncMock(return_value=True))
    monkeypatch.setattr(users_repository, "touch_last_seen", AsyncMock())

    query = SimpleNamespace(answer=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        callback_query=query,
        effective_chat=SimpleNamespace(id=42),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    with pytest.raises(ApplicationHandlerStop):
        await global_gate.enforce_ban_and_track_activity(update, context)

    query.answer.assert_awaited_once_with(global_gate._BANNED_MESSAGE, show_alert=True)
    context.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_banned_user_still_stops_even_if_notification_fails(monkeypatch):
    """اولویت با توقف پردازش است، نه موفقیت اطلاع‌رسانی — یک خطای شبکه‌ی
    گذرا در ارسال پیام نباید یعنی کاربر بن‌شده از دروازه رد شود."""
    monkeypatch.setattr(users_repository, "is_banned", AsyncMock(return_value=True))
    monkeypatch.setattr(users_repository, "touch_last_seen", AsyncMock())

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        callback_query=None,
        effective_chat=SimpleNamespace(id=42),
    )
    context = SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError("network boom")))
    )

    with pytest.raises(ApplicationHandlerStop):
        await global_gate.enforce_ban_and_track_activity(update, context)


@pytest.mark.asyncio
async def test_non_banned_user_touches_last_seen_and_does_not_stop(monkeypatch):
    monkeypatch.setattr(users_repository, "is_banned", AsyncMock(return_value=False))
    touch_mock = AsyncMock()
    monkeypatch.setattr(users_repository, "touch_last_seen", touch_mock)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=99), callback_query=None)
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))

    await global_gate.enforce_ban_and_track_activity(update, context)  # نباید استثنایی بیندازد

    touch_mock.assert_awaited_once_with(99)


@pytest.mark.asyncio
async def test_update_without_effective_user_is_ignored(monkeypatch):
    """برخی آپدیت‌های نادر (مثل poll_answer ناشناس) ممکن است effective_user
    نداشته باشند — دروازه نباید در این حالت خطا بدهد."""
    is_banned_mock = AsyncMock()
    monkeypatch.setattr(users_repository, "is_banned", is_banned_mock)

    update = SimpleNamespace(effective_user=None)
    context = SimpleNamespace()

    await global_gate.enforce_ban_and_track_activity(update, context)

    is_banned_mock.assert_not_called()
