# tests/test_membership.py
#
# تست رگرسیون یک باگ قدیمی (کشف‌شده در ممیزی):
# check_membership() بعد از تایید موفق عضویت start(update, context) را صدا
# می‌زند، ولی خودِ آپدیت از یک callback_query می‌آید — یعنی update.message
# برابر None است. قبلاً start() از update.message.reply_text استفاده
# می‌کرد که این مسیر را می‌شکست.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import app_connection  # noqa: E402
from bme_bot.handlers import membership  # noqa: E402


class FakeMessage:
    """پیامی که هم روی update.callback_query.message و هم (با کمک
    SimpleNamespace) به‌عنوان update.effective_message در دسترس است."""

    def __init__(self):
        self.replies = []

    async def reply_text(self, text, reply_markup=None, **kwargs):
        self.replies.append(text)


@pytest_asyncio.fixture
async def temp_users_db(tmp_path, monkeypatch):
    """جدول‌های واقعی را از طریق خودِ setup_users_database می‌سازد (نه یک
    schema دستی جدا) — یک schema دستی مستقل اینجا زمانی از schema واقعی
    (که ستون‌های is_banned/joined_at/last_seen_at بهش اضافه شد) عقب افتاد و
    یک تست را شکست. استفاده از تابع واقعی یعنی این‌جور واگرایی دیگر ممکن
    نیست."""
    db_path = tmp_path / "users_test.db"
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    await app_connection.setup_users_database()
    return db_path


@pytest.mark.asyncio
async def test_check_membership_reaches_welcome_message_after_callback_query(temp_users_db):
    """بازتولید دقیق سناریوی واقعی: کاربری که قبلاً بلاک شده بود، عضو گروه
    می‌شود و روی «✅ عضو شدم» می‌زند. این نباید AttributeError بدهد و باید
    پیام خوش‌آمدگویی واقعی را ببیند (نه پیام خطای عمومی)."""

    fake_message = FakeMessage()
    query = SimpleNamespace(
        data="check_membership",
        from_user=SimpleNamespace(id=42, username="tester"),
        answer=AsyncMock(),
        delete_message=AsyncMock(),
        message=fake_message,
    )

    # دقیقاً مثل واقعیت python-telegram-bot: وقتی آپدیت از callback_query
    # می‌آید، update.message برابر None است؛ فقط effective_message پر است.
    update = SimpleNamespace(
        callback_query=query,
        message=None,
        effective_user=SimpleNamespace(id=42, username="tester"),
        effective_chat=SimpleNamespace(id=42),
        effective_message=fake_message,
    )

    context = SimpleNamespace(
        bot=SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
        )
    )

    await membership.check_membership(update, context)  # نباید هیچ استثنایی بیندازد

    assert query.answer.await_count == 1
    assert query.delete_message.await_count == 1
    assert len(fake_message.replies) == 1
    assert "خوش آمدید" in fake_message.replies[0]
