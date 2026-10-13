# tests/test_admin_recent_errors.py
#
# پوشش «🪲 خطاهای اخیر» در پنل ادمین — نمای فشرده‌ی error_log. بقیه‌ی
# توابع نمایشیِ «سلامت سیستم» (که این فایل ازشون الگو گرفته) فعلاً تست
# مستقیم ندارن (رجوع به یادداشت مشابه در test_ai_assistant_streaming.py)؛
# این فایل فقط افزوده‌ی بند ۷ رو پوشش می‌ده.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import error_log_repository  # noqa: E402
from bme_bot.handlers import admin  # noqa: E402


@pytest.mark.asyncio
async def test_format_recent_errors_message_when_empty(monkeypatch):
    monkeypatch.setattr(error_log_repository, "get_recent_errors", AsyncMock(return_value=[]))

    text = await admin._format_recent_errors_message()

    assert "هیچ خطای" in text


@pytest.mark.asyncio
async def test_format_recent_errors_message_lists_each_error_compactly(monkeypatch):
    monkeypatch.setattr(
        error_log_repository, "get_recent_errors",
        AsyncMock(return_value=[
            {
                "fingerprint": "TypeError@a.py:1", "exception_type": "TypeError", "location": "a.py:1",
                "count": 7, "first_seen": "2026-09-01T10:00:00", "last_seen": "2026-09-20T14:23:07.123456+00:00",
                "sample_traceback": "Traceback (most recent call last):\n  ...\nTypeError: boom",
            },
        ]),
    )

    text = await admin._format_recent_errors_message()

    assert "TypeError" in text
    assert "7×" in text or "۷×" in text
    assert "a.py:1" in text
    assert "TypeError: boom" in text  # آخرین خط traceback نمونه
    # میکروثانیه/timezone نباید توی نمای فشرده دیده بشه.
    assert "123456" not in text
    assert "2026-09-20 14:23" in text


@pytest.mark.asyncio
async def test_recent_errors_menu_callback_routes_correctly(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])
    monkeypatch.setattr(error_log_repository, "get_recent_errors", AsyncMock(return_value=[]))
    query = SimpleNamespace(data="admin_menu:recent_errors", edit_message_text=AsyncMock(), answer=AsyncMock())
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=42))
    context = SimpleNamespace()

    await admin.handle_admin_menu_callback(update, context)

    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.call_args
    assert "هیچ خطای" in args[0]
    assert kwargs["reply_markup"] is not None
