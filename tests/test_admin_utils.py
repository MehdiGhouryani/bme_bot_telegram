# tests/test_admin_utils.py
#
# تست‌های notify_admins: باید ارسال به هر ادمین را
# مستقل از بقیه محافظت کند — قبلاً suggestion.py این محافظت را نداشت.

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import admins_repository, app_connection  # noqa: E402
from bme_bot.utils import admin as admin_utils  # noqa: E402
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


# --- ادمین‌های دینامیک (پنل «مدیریت ادمین‌ها») ---

@pytest_asyncio.fixture
async def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    await app_connection.setup_users_database()
    return db_path


def test_is_admin_true_for_static_env_list(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111"])
    assert admin_utils.is_admin(111) is True
    assert admin_utils.is_admin(222) is False


def test_is_admin_true_for_dynamically_added_admin(monkeypatch):
    """ادمینی که فقط از طریق افزودن دینامیک اضافه شده (نه تو ADMIN_CHAT_ID
    استاتیک)، باید is_admin() رو هم True بگیره — همون تابعی که همه‌ی
    فیچرهای بات (equipment/quiz/ocr/stt/...) باهاش چک می‌کنن."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111"])
    admin_utils._dynamic_admin_ids.add("777")

    assert admin_utils.is_admin(777) is True
    assert admin_utils.is_admin(888) is False


def test_is_main_admin_only_true_for_configured_main_admin(monkeypatch):
    """ادمین دینامیک، و حتی یه ادمین دیگه تو فهرست استاتیک، نباید
    is_main_admin بشن — فقط MAIN_ADMIN_CHAT_ID."""
    monkeypatch.setattr(config, "MAIN_ADMIN_CHAT_ID", "111")
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111", "222"])
    admin_utils._dynamic_admin_ids.add("777")

    assert admin_utils.is_main_admin(111) is True
    assert admin_utils.is_main_admin(222) is False
    assert admin_utils.is_main_admin(777) is False


def test_is_main_admin_false_when_not_configured(monkeypatch):
    monkeypatch.setattr(config, "MAIN_ADMIN_CHAT_ID", None)
    assert admin_utils.is_main_admin(111) is False


@pytest.mark.asyncio
async def test_load_dynamic_admins_populates_cache_from_db(temp_users_db):
    await admins_repository.add_admin(777, added_by=111)
    await admins_repository.add_admin(888, added_by=111)
    assert admin_utils._dynamic_admin_ids == set()  # قبل از load، کش خالیه

    await admin_utils.load_dynamic_admins()

    assert admin_utils._dynamic_admin_ids == {"777", "888"}


@pytest.mark.asyncio
async def test_add_dynamic_admin_persists_and_updates_cache_immediately(temp_users_db):
    """بدون نیاز به ریستارت بات — هم دیتابیس هم کش همون لحظه به‌روز می‌شن."""
    await admin_utils.add_dynamic_admin(777, added_by=111)

    assert admin_utils.is_admin(777) is True
    stored = await admins_repository.list_admins()
    assert stored == [{"user_id": 777, "added_by": 111, "added_at": stored[0]["added_at"]}]


@pytest.mark.asyncio
async def test_remove_dynamic_admin_persists_and_updates_cache_immediately(temp_users_db):
    await admin_utils.add_dynamic_admin(777, added_by=111)

    removed = await admin_utils.remove_dynamic_admin(777)

    assert removed is True
    assert admin_utils.is_admin(777) is False
    assert await admins_repository.list_admins() == []


@pytest.mark.asyncio
async def test_remove_dynamic_admin_returns_false_when_not_an_admin(temp_users_db):
    removed = await admin_utils.remove_dynamic_admin(999)
    assert removed is False


@pytest.mark.asyncio
async def test_notify_admins_includes_dynamic_admins_alongside_static_list(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111"])
    admin_utils._dynamic_admin_ids.add("777")
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    await notify_admins(context, "پیام تست")

    assert ("111", "پیام تست") in bot.sent
    assert ("777", "پیام تست") in bot.sent
    assert len(bot.sent) == 2


@pytest.mark.asyncio
async def test_notify_admins_does_not_duplicate_when_same_id_in_both_lists(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111"])
    admin_utils._dynamic_admin_ids.add("111")
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    await notify_admins(context, "پیام تست")

    assert bot.sent == [("111", "پیام تست")]
