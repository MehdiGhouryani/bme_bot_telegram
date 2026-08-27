# tests/test_telegram_error_handler.py
#
# تست TelegramAdminErrorHandler: نادیده‌گرفتن لاگرهای exclude شده، throttle
# پیام‌های تکراری، زمان‌بندی ارسال async از دل emit سینک، و این‌که شکست
# خودِ ارسال هرگز به بیرون نشت نمی‌کند (محافظت در برابر حلقه).

import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.utils import telegram_error_handler  # noqa: E402


def _make_record(name="some.module", msg="something broke", level=logging.ERROR):
    return logging.LogRecord(
        name=name, level=level, pathname=__file__, lineno=1,
        msg=msg, args=(), exc_info=None,
    )


async def _drain_pending_tasks():
    """emit() یک asyncio.Task زمان‌بندی می‌کند که خودش هم await دیگری
    (ارسال fake_bot.send_message) دارد. یک sleep(0) فقط یک چرخه از لوپ رو
    عبور می‌ده که ممکنه برای تسک‌های دو-مرحله‌ای کافی نباشه؛ این تابع همه‌ی
    تسک‌های در حال انتظار رو صریحاً منتظر می‌مونه تا کامل تموم بشن - جلوی
    هر ریسک «Event loop is closed» در پایان تست رو می‌گیره."""
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


@pytest.fixture(autouse=True)
def _reset_handler_state(monkeypatch):
    monkeypatch.setattr(config, "MAIN_ADMIN_CHAT_ID", "999")
    fake_bot = AsyncMock()
    telegram_error_handler.set_bot(fake_bot)
    yield fake_bot
    telegram_error_handler.set_bot(None)


@pytest.mark.asyncio
async def test_excluded_logger_names_are_never_forwarded(_reset_handler_state):
    fake_bot = _reset_handler_state
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record(name="bme_bot.utils.error_reporting"))
    handler.emit(_make_record(name=telegram_error_handler.__name__))
    await _drain_pending_tasks()

    fake_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_error_from_normal_module_is_forwarded(_reset_handler_state):
    fake_bot = _reset_handler_state
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record(name="bme_bot.services.some_service", msg="یه خطای واقعی"))
    await _drain_pending_tasks()

    fake_bot.send_message.assert_awaited_once()
    _, kwargs = fake_bot.send_message.call_args
    assert kwargs["chat_id"] == "999"
    assert "یه خطای واقعی" in kwargs["text"]
    assert "bme_bot.services.some_service" in kwargs["text"]


@pytest.mark.asyncio
async def test_throttle_blocks_duplicate_within_window(_reset_handler_state):
    fake_bot = _reset_handler_state
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record(msg="خطای تکراری"))
    handler.emit(_make_record(msg="خطای تکراری"))
    handler.emit(_make_record(msg="خطای تکراری"))
    await _drain_pending_tasks()

    fake_bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_different_messages_are_not_throttled_together(_reset_handler_state):
    fake_bot = _reset_handler_state
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record(msg="خطای اول"))
    handler.emit(_make_record(msg="خطای کاملاً متفاوت دوم"))
    await _drain_pending_tasks()

    assert fake_bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_no_bot_set_does_not_crash():
    telegram_error_handler.set_bot(None)
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record())  # نباید استثنا بندازه
    await _drain_pending_tasks()


@pytest.mark.asyncio
async def test_no_main_admin_configured_does_not_crash(monkeypatch, _reset_handler_state):
    fake_bot = _reset_handler_state
    monkeypatch.setattr(config, "MAIN_ADMIN_CHAT_ID", None)
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record())
    await _drain_pending_tasks()

    fake_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_failure_is_swallowed_silently(_reset_handler_state):
    fake_bot = _reset_handler_state
    fake_bot.send_message.side_effect = RuntimeError("Telegram API down")
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record())
    await _drain_pending_tasks()  # نباید استثنای ناگرفته بندازه بیرون


@pytest.mark.asyncio
async def test_long_message_is_truncated(_reset_handler_state):
    fake_bot = _reset_handler_state
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record(msg="خ" * 10000))
    await _drain_pending_tasks()

    _, kwargs = fake_bot.send_message.call_args
    assert len(kwargs["text"]) < 4096


def test_emit_without_running_loop_does_not_raise(_reset_handler_state):
    """اگه هیچ event loop در حال اجرا نباشه (مثلاً یه logger.error خیلی
    زودهنگام قبل از شروع بات)، emit نباید کرش کنه، فقط بی‌صدا رد بشه."""
    handler = telegram_error_handler.TelegramAdminErrorHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.emit(_make_record())  # sync، بدون asyncio.run/pytest.mark.asyncio
