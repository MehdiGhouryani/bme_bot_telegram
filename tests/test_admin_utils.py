# tests/test_admin_utils.py
#
# تست‌های notify_admins: باید ارسال به هر ادمین را
# مستقل از بقیه محافظت کند — قبلاً suggestion.py این محافظت را نداشت.

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.utils.admin import notify_admins  # noqa: E402
from bme_bot.handlers import suggestion  # noqa: E402


class FakeBot:
    def __init__(self, fail_for=None):
        self.fail_for = fail_for or set()
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None):
        if chat_id in self.fail_for:
            raise RuntimeError(f"simulated failure for {chat_id}")
        self.sent.append((chat_id, text))


@pytest.mark.asyncio
async def test_notify_admins_sends_to_all(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111", "222"])
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    await notify_admins(context, "پیام تست")

    assert bot.sent == [("111", "پیام تست"), ("222", "پیام تست")]


@pytest.mark.asyncio
async def test_notify_admins_one_failure_does_not_block_others(monkeypatch):
    """یافته‌ی ۷: اگر ارسال به یک ادمین شکست بخورد، بقیه‌ی ادمین‌ها همچنان
    پیام را دریافت می‌کنند."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111", "222", "333"])
    bot = FakeBot(fail_for={"222"})
    context = SimpleNamespace(bot=bot)

    await notify_admins(context, "پیام تست")

    assert ("111", "پیام تست") in bot.sent
    assert ("333", "پیام تست") in bot.sent
    assert not any(c == "222" for c, _ in bot.sent)


@pytest.mark.asyncio
async def test_notify_admins_empty_list_does_not_raise(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", [])
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    await notify_admins(context, "پیام تست")  # نباید استثنایی بیندازد
    assert bot.sent == []


@pytest.mark.asyncio
async def test_suggestion_message_still_thanks_user_even_if_an_admin_send_fails(monkeypatch):
    """یافته‌ی ۷ در عمل: قبلاً اگر ارسال به یک ادمین شکست می‌خورد، کاربر هرگز
    پیام «ممنون از پیشنهادتون» را نمی‌دید. حالا باید همیشه ببیند."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111", "222"])
    bot = FakeBot(fail_for={"111"})

    replies = []

    class FakeMessage:
        text = "لطفاً حالت شب اضافه کنید"
        from_user = SimpleNamespace(full_name="Test User", username="testuser", id=42)

        async def reply_text(self, text):
            replies.append(text)

    update = SimpleNamespace(message=FakeMessage())
    context = SimpleNamespace(bot=bot, user_data={"awaiting_request": True})

    await suggestion.handle_suggestion_message(update, context)

    assert replies == ["ممنون از پیشنهادتون! ما اون رو بررسی خواهیم کرد."]
    assert context.user_data["awaiting_request"] is False
    assert ("222", ) == tuple(c for c, _ in bot.sent)  # ادمین ۲۲۲ پیام را دریافت کرد، ۱۱۱ شکست خورد
