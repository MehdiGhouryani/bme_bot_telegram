# tests/test_admin.py
#
# تست admin.py — منوی /admin، آمار، جستجو+بن (با ConversationHandler)،
# Broadcast (با ConversationHandler). تست فقط برای کدی نوشته می‌شود که
# مستقیم تغییر می‌کند، نه به‌عنوان یک ابتکار پوشش عمومی جدا.
#
# سطح این تست‌ها: مستقیماً توابع هندلر را با آپدیت/context ساختگی (SimpleNamespace)
# صدا می‌زند و رفتار (پیام‌ها، callback ها به repository، مقدار state
# برگشتی) را چک می‌کند — نه شبیه‌سازی کامل ماشین‌حالت PTB (که خودِ کتابخانه
# آن را جداگانه و به‌طور کامل تست کرده؛ اینجا فقط منطق سفارشی ما تست می‌شود).

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import admin_actions_repository, feature_usage_repository, users_repository  # noqa: E402
from bme_bot.handlers import admin  # noqa: E402
from telegram.error import Forbidden  # noqa: E402
from telegram.ext import ConversationHandler  # noqa: E402


def _admin_update(callback_data=None, text=None, user_id=999):
    """آپدیت ساختگی که هم برای callback_query هم برای پیام متنی کار می‌کند."""
    replies = []
    edits = []

    class FakeMessage:
        async def reply_text(self, text_, **kwargs):
            replies.append(text_)

        async def reply_photo(self, **kwargs):
            replies.append(kwargs)

    message = FakeMessage()

    query = None
    if callback_data is not None:
        query = SimpleNamespace(
            data=callback_data,
            answer=AsyncMock(),
            edit_message_text=AsyncMock(side_effect=lambda t, **kw: edits.append(("text", t))),
            edit_message_caption=AsyncMock(side_effect=lambda **kw: edits.append(("caption", kw.get("caption")))),
        )

    update = SimpleNamespace(
        callback_query=query,
        message=message if text is not None else SimpleNamespace(
            text=None, photo=None, caption=None, reply_text=AsyncMock()
        ),
        effective_user=SimpleNamespace(id=user_id),
        effective_message=message,
    )
    if text is not None:
        message.text = text

    return update, replies, edits


def _context(user_data=None):
    return SimpleNamespace(
        bot=SimpleNamespace(send_message=AsyncMock(), send_photo=AsyncMock()),
        user_data=user_data if user_data is not None else {},
    )


@pytest.fixture(autouse=True)
def _admin_ids(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])


# ============================== منوی اصلی ==============================

@pytest.mark.asyncio
async def test_open_admin_panel_shows_menu_for_admin():
    update, replies, _ = _admin_update(text="/admin")
    context = _context()

    await admin.open_admin_panel(update, context)

    assert len(replies) == 1
    assert "پنل مدیریت" in replies[0]


@pytest.mark.asyncio
async def test_open_admin_panel_rejects_non_admin():
    update, replies, _ = _admin_update(text="/admin", user_id=111)
    context = _context()

    await admin.open_admin_panel(update, context)

    assert replies == [admin._NOT_ADMIN_MESSAGE]


@pytest.mark.asyncio
async def test_handle_admin_menu_callback_rejects_non_admin():
    update, _, _ = _admin_update(callback_data="admin_menu:stats", user_id=111)
    context = _context()

    await admin.handle_admin_menu_callback(update, context)

    update.callback_query.answer.assert_awaited_once_with(admin._NOT_ADMIN_MESSAGE, show_alert=True)


@pytest.mark.asyncio
async def test_handle_admin_menu_callback_stats_shows_numbers(monkeypatch):
    monkeypatch.setattr(users_repository, "get_user_stats", AsyncMock(return_value={
        "total": 10, "new_today": 1, "new_week": 2, "new_month": 3,
        "active_7d": 4, "active_30d": 5, "banned": 1,
    }))
    monkeypatch.setattr(feature_usage_repository, "get_feature_counts", AsyncMock(return_value={"ai": 7}))

    update, _, edits = _admin_update(callback_data="admin_menu:stats")
    context = _context()

    await admin.handle_admin_menu_callback(update, context)

    assert len(edits) == 1
    assert "کل کاربران: 10" in edits[0][1]
    assert "ai: 7" in edits[0][1]


def test_format_breakdown_section_handles_empty_data():
    """وقتی هنوز هیچ detail ای برای یک فیچر/بازه ثبت نشده، باید همان پیام
    «هنوز داده‌ای ثبت نشده» را نشان دهد — هم‌سبک با _format_stats_message
    برای پربازدیدترین بخش‌ها."""
    lines = admin._format_breakdown_section("عنوان آزمایشی", {})
    assert lines == ["عنوان آزمایشی", "(هنوز داده‌ای ثبت نشده)"]


def test_format_breakdown_section_computes_percentages():
    lines = admin._format_breakdown_section(
        "عنوان", {"gemini/gemini-2.5-flash": 3, "groq/some-model": 1}
    )
    assert lines == [
        "عنوان",
        "• gemini/gemini-2.5-flash: 3 (75%)",
        "• groq/some-model: 1 (25%)",
    ]


@pytest.mark.asyncio
async def test_handle_admin_menu_callback_health_shows_provider_breakdown(monkeypatch):
    """اتصال get_detail_breakdown موجود به دکمه‌ی «سلامت سیستم»."""
    async def fake_breakdown(feature, days=None):
        if feature == "ai":
            return {"gemini/gemini-2.5-flash": 3, "groq/some-model": 1}
        return {"google_vision": 2}

    monkeypatch.setattr(feature_usage_repository, "get_detail_breakdown", fake_breakdown)

    update, _, edits = _admin_update(callback_data="admin_menu:health")
    context = _context()

    await admin.handle_admin_menu_callback(update, context)

    assert len(edits) == 1
    text = edits[0][1]
    assert "🩺 سلامت سیستم" in text
    assert "gemini/gemini-2.5-flash: 3 (75%)" in text
    assert "google_vision: 2 (100%)" in text


@pytest.mark.asyncio
async def test_send_daily_summary_includes_feature_counts_and_breakdowns(monkeypatch):
    """خلاصه‌ی روزانه باید هم تعامل بر اساس فیچر (شامل ai_failure/ocr_failure)
    هم شکست AI/OCR بر اساس provider را نشان دهد — با همان
    _format_breakdown_section مشترک."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])

    async def fake_feature_counts(days=None):
        return {"equipment": 40, "ai": 12, "ai_failure": 2}

    async def fake_breakdown(feature, days=None):
        if feature == "ai":
            return {"gemini/gemini-2.5-flash": 10, "groq/some-model": 2}
        return {}

    monkeypatch.setattr(feature_usage_repository, "get_feature_counts", fake_feature_counts)
    monkeypatch.setattr(feature_usage_repository, "get_detail_breakdown", fake_breakdown)

    bot = SimpleNamespace(send_message=AsyncMock())
    context = SimpleNamespace(bot=bot)

    await admin.send_daily_summary(context)

    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.kwargs["text"]
    assert "📅 خلاصه‌ی روزانه" in text
    assert "ai_failure: 2" in text
    assert "gemini/gemini-2.5-flash: 10 (83%)" in text


@pytest.mark.asyncio
async def test_handle_admin_menu_callback_users_shows_submenu():
    update, _, edits = _admin_update(callback_data="admin_menu:users")
    context = _context()

    await admin.handle_admin_menu_callback(update, context)

    assert edits[0][1] == "مدیریت کاربران:"


# ============================== جستجو + بن ==============================

@pytest.mark.asyncio
async def test_start_user_search_rejects_non_admin():
    update, _, _ = _admin_update(callback_data="admin_users_search_start", user_id=111)
    context = _context()

    result = await admin.start_user_search(update, context)

    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_start_user_search_prompts_admin():
    update, _, edits = _admin_update(callback_data="admin_users_search_start")
    context = _context()

    result = await admin.start_user_search(update, context)

    assert result == admin.SEARCH_AWAITING_QUERY
    assert "شناسه" in edits[0][1]


@pytest.mark.asyncio
async def test_receive_search_query_no_results(monkeypatch):
    monkeypatch.setattr(users_repository, "search_user", AsyncMock(return_value=[]))
    update, replies, _ = _admin_update(text="ghost_user")
    context = _context()

    result = await admin.receive_search_query(update, context)

    assert result == admin.SEARCH_AWAITING_QUERY
    assert "پیدا نشد" in replies[0]


@pytest.mark.asyncio
async def test_receive_search_query_multiple_results_asks_to_narrow(monkeypatch):
    monkeypatch.setattr(users_repository, "search_user", AsyncMock(return_value=[
        {"user_id": 1, "username": "a"}, {"user_id": 2, "username": "b"},
    ]))
    update, replies, _ = _admin_update(text="a")
    context = _context()

    result = await admin.receive_search_query(update, context)

    assert result == admin.SEARCH_AWAITING_QUERY
    assert "2 کاربر پیدا شد" in replies[0]


@pytest.mark.asyncio
async def test_receive_search_query_single_result_shows_profile(monkeypatch):
    profile = {
        "user_id": 42, "username": "alice", "chat_id": "42",
        "is_banned": 0, "joined_at": "2026-01-01", "last_seen_at": "2026-01-02",
    }
    monkeypatch.setattr(users_repository, "search_user", AsyncMock(return_value=[profile]))
    update, replies, _ = _admin_update(text="42")
    context = _context()

    result = await admin.receive_search_query(update, context)

    assert result == admin.SEARCH_AWAITING_QUERY
    assert "@alice" in replies[0]
    assert "✅ فعال" in replies[0]


# --- _format_profile: entity date_time (Bot API 10.x، بدون نیاز به پرمیوم) ---

def test_format_profile_builds_date_time_entities_for_valid_utc_strings():
    """joined_at/last_seen_at با همون فرمتی که users_repository.py واقعاً
    ذخیره می‌کنه (%Y-%m-%d %H:%M:%S، UTC) — باید دو تا entity واقعی
    date_time بسازه، نه فقط متن خام."""
    profile = {
        "user_id": 42, "username": "alice", "chat_id": "42", "is_banned": 0,
        "joined_at": "2026-01-01 10:00:00", "last_seen_at": "2026-08-20 15:30:00",
    }

    text, entities = admin._format_profile(profile)

    assert len(entities) == 2
    assert all(e.type == "date_time" for e in entities)
    joined_entity, last_seen_entity = entities
    assert joined_entity.to_dict()["unix_time"] == 1767261600  # 2026-01-01 10:00:00 UTC
    assert last_seen_entity.to_dict()["unix_time"] == 1787239800  # 2026-08-20 15:30:00 UTC
    # آفست/طول باید واقعاً روی همون substring تاریخ تو متن نهایی بشینه —
    # با شمارش UTF-16 واقعی (نه فرض ثابت تعداد واحد به‌ازای هر ایموجی —
    # 👤/🚫 خارج از BMP و ۲ واحدند، ولی ✅ داخل BMP و فقط ۱ واحده)، نه
    # len() خام پایتون.
    encoded = text.encode("utf-16-le")
    joined_slice = encoded[joined_entity.offset * 2: (joined_entity.offset + joined_entity.length) * 2]
    assert joined_slice.decode("utf-16-le") == "2026-01-01 10:00:00"


def test_format_profile_falls_back_to_plain_text_for_unparseable_date():
    """فرمت غیرمنتظره (مثلاً داده‌ی قدیمی/فقط-تاریخ) نباید کل پیام پروفایل
    رو بشکنه — فقط entity ساخته نمی‌شه، متن خام همچنان نمایش داده می‌شه."""
    profile = {
        "user_id": 42, "username": "alice", "chat_id": "42", "is_banned": 0,
        "joined_at": "2026-01-01", "last_seen_at": None,
    }

    text, entities = admin._format_profile(profile)

    assert entities == []
    assert "2026-01-01" in text
    assert "نامشخص" in text  # last_seen_at=None


@pytest.mark.asyncio
async def test_receive_search_query_passes_entities_to_reply_text(monkeypatch):
    profile = {
        "user_id": 42, "username": "alice", "chat_id": "42",
        "is_banned": 0, "joined_at": "2026-01-01 10:00:00", "last_seen_at": "2026-08-20 15:30:00",
    }
    monkeypatch.setattr(users_repository, "search_user", AsyncMock(return_value=[profile]))
    captured_kwargs = {}

    class FakeMessage:
        async def reply_text(self, text_, **kwargs):
            captured_kwargs.update(kwargs)

    update = SimpleNamespace(message=FakeMessage(), effective_user=SimpleNamespace(id=999))
    update.message.text = "42"
    context = _context()

    await admin.receive_search_query(update, context)

    assert len(captured_kwargs.get("entities", [])) == 2


@pytest.mark.asyncio
async def test_remind_text_needed_for_non_text_input_during_search():
    """مصرف‌کننده‌ی state SEARCH_AWAITING_QUERY، نه فقط receive_search_query."""
    replies = []

    class FakeMessage:
        async def reply_text(self, text_, **kwargs):
            replies.append(text_)

    update = SimpleNamespace(message=FakeMessage())
    context = _context()

    result = await admin.remind_text_needed(update, context)

    assert result == admin.SEARCH_AWAITING_QUERY
    assert "شناسه" in replies[0] or "نام‌کاربری" in replies[0]


@pytest.mark.asyncio
async def test_toggle_ban_bans_user_and_logs_action(monkeypatch):
    set_banned_mock = AsyncMock()
    log_action_mock = AsyncMock()
    monkeypatch.setattr(users_repository, "set_banned", set_banned_mock)
    monkeypatch.setattr(admin_actions_repository, "log_action", log_action_mock)
    monkeypatch.setattr(users_repository, "search_user", AsyncMock(return_value=[{
        "user_id": 42, "username": "alice", "chat_id": "42",
        "is_banned": 1, "joined_at": "2026-01-01", "last_seen_at": "2026-01-02",
    }]))

    update, _, edits = _admin_update(callback_data="admin_toggle_ban:42:ban")
    context = _context()

    result = await admin.toggle_ban(update, context)

    set_banned_mock.assert_awaited_once_with(42, True)
    log_action_mock.assert_awaited_once_with(999, "ban_user", target="42")
    assert result == admin.SEARCH_AWAITING_QUERY
    assert "🚫 مسدود" in edits[0][1]


@pytest.mark.asyncio
async def test_toggle_ban_unban_logs_correct_action(monkeypatch):
    monkeypatch.setattr(users_repository, "set_banned", AsyncMock())
    log_action_mock = AsyncMock()
    monkeypatch.setattr(admin_actions_repository, "log_action", log_action_mock)
    monkeypatch.setattr(users_repository, "search_user", AsyncMock(return_value=[{
        "user_id": 42, "username": "alice", "chat_id": "42",
        "is_banned": 0, "joined_at": None, "last_seen_at": None,
    }]))

    update, _, _ = _admin_update(callback_data="admin_toggle_ban:42:unban")
    context = _context()

    await admin.toggle_ban(update, context)

    log_action_mock.assert_awaited_once_with(999, "unban_user", target="42")


@pytest.mark.asyncio
async def test_toggle_ban_refuses_to_ban_another_admin(monkeypatch):
    """بن‌کردن یک ادمین دیگر باید رد شود، وگرنه دروازه‌ی سراسری آن ادمین را
    حتی از /admin هم قفل می‌کند."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999", "777"])  # 777 هم ادمین است
    set_banned_mock = AsyncMock()
    log_action_mock = AsyncMock()
    monkeypatch.setattr(users_repository, "set_banned", set_banned_mock)
    monkeypatch.setattr(admin_actions_repository, "log_action", log_action_mock)

    update, _, _ = _admin_update(callback_data="admin_toggle_ban:777:ban")
    context = _context()

    result = await admin.toggle_ban(update, context)

    set_banned_mock.assert_not_called()
    log_action_mock.assert_not_called()
    update.callback_query.answer.assert_awaited_once_with(
        "نمی‌توانید یک ادمین دیگر را مسدود کنید.", show_alert=True
    )
    assert result == admin.SEARCH_AWAITING_QUERY


@pytest.mark.asyncio
async def test_toggle_ban_allows_unbanning_an_admin(monkeypatch):
    """رفع بن از یک ادمین (که اصلاً نباید بن شده باشد، ولی احتیاط) نباید رد
    شود — فقط جهت bann کردن مسدود است."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999", "777"])
    set_banned_mock = AsyncMock()
    monkeypatch.setattr(users_repository, "set_banned", set_banned_mock)
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())
    monkeypatch.setattr(users_repository, "search_user", AsyncMock(return_value=[{
        "user_id": 777, "username": "other_admin", "chat_id": "777",
        "is_banned": 1, "joined_at": None, "last_seen_at": None,
    }]))

    update, _, _ = _admin_update(callback_data="admin_toggle_ban:777:unban")
    context = _context()

    await admin.toggle_ban(update, context)

    set_banned_mock.assert_awaited_once_with(777, False)


@pytest.mark.asyncio
async def test_end_search_via_callback():
    update, _, edits = _admin_update(callback_data="admin_search_end")
    context = _context()

    result = await admin.end_search(update, context)

    assert result == ConversationHandler.END
    assert edits[0][1] == "پایان جستجو."


@pytest.mark.asyncio
async def test_end_search_via_cancel_command():
    update, replies, _ = _admin_update(text="/cancel")
    context = _context()

    result = await admin.end_search(update, context)

    assert result == ConversationHandler.END
    assert replies == ["پایان جستجو."]


# ============================== Broadcast ==============================

@pytest.mark.asyncio
async def test_start_broadcast_rejects_non_admin():
    update, _, _ = _admin_update(callback_data="admin_menu:broadcast", user_id=111)
    context = _context()

    result = await admin.start_broadcast(update, context)

    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_start_broadcast_prompts_for_photo():
    update, _, edits = _admin_update(callback_data="admin_menu:broadcast")
    context = _context()

    result = await admin.start_broadcast(update, context)

    assert result == admin.BROADCAST_AWAITING_PHOTO
    assert "عکس" in edits[0][1]


@pytest.mark.asyncio
async def test_receive_broadcast_photo_stores_data_and_shows_preview():
    replies = []

    class FakeMessage:
        photo = [SimpleNamespace(file_id="photo123")]
        caption = "متن آزمایشی"

        async def reply_photo(self, **kwargs):
            replies.append(kwargs)

    update = SimpleNamespace(message=FakeMessage())
    context = _context()

    result = await admin.receive_broadcast_photo(update, context)

    assert result == admin.BROADCAST_AWAITING_CONFIRMATION
    assert context.user_data["broadcast_photo_file_id"] == "photo123"
    assert context.user_data["broadcast_caption"] == "متن آزمایشی"
    assert replies[0]["photo"] == "photo123"
    assert "متن آزمایشی" in replies[0]["caption"]


@pytest.mark.asyncio
async def test_remind_photo_needed_when_text_sent_instead_of_photo():
    update, replies, _ = _admin_update(text="یک متن به‌جای عکس")
    context = _context()

    result = await admin.remind_photo_needed(update, context)

    assert result == admin.BROADCAST_AWAITING_PHOTO
    assert "عکس" in replies[0]


@pytest.mark.asyncio
async def test_cancel_broadcast_via_callback_clears_user_data():
    update, _, edits = _admin_update(callback_data="admin_broadcast_cancel")
    context = _context(user_data={"broadcast_photo_file_id": "x", "broadcast_caption": "y"})

    result = await admin.cancel_broadcast(update, context)

    assert result == ConversationHandler.END
    assert "broadcast_photo_file_id" not in context.user_data
    assert edits[0] == ("caption", "❌ لغو شد.")


@pytest.mark.asyncio
async def test_cancel_broadcast_via_cancel_command():
    update, replies, _ = _admin_update(text="/cancel")
    context = _context(user_data={"broadcast_photo_file_id": "x"})

    result = await admin.cancel_broadcast(update, context)

    assert result == ConversationHandler.END
    assert replies == ["❌ لغو شد."]


@pytest.mark.asyncio
async def test_confirm_and_send_broadcast_launches_background_task(monkeypatch):
    """اینجا فقط تایید می‌شود که تسک پس‌زمینه واقعاً launch می‌شود و
    conversation فوراً END برمی‌گرداند (بدون معطل‌ماندن ادمین تا پایان کل
    ارسال) — منطق واقعی ارسال (_broadcast_worker) جداگانه تست شده."""
    worker_called_with = {}

    async def fake_worker(context, admin_id, photo_file_id, caption):
        worker_called_with["admin_id"] = admin_id
        worker_called_with["photo_file_id"] = photo_file_id
        worker_called_with["caption"] = caption

    monkeypatch.setattr(admin, "_broadcast_worker", fake_worker)

    update, _, edits = _admin_update(callback_data="admin_broadcast_confirm")
    context = _context(user_data={"broadcast_photo_file_id": "photo123", "broadcast_caption": "سلام"})

    result = await admin.confirm_and_send_broadcast(update, context)
    assert result == ConversationHandler.END
    assert "photo_file_id" not in context.user_data.get("broadcast_photo_file_id", {})  # پاک شد

    await asyncio.sleep(0)  # به تسک پس‌زمینه فرصت اجرا بدهیم

    assert worker_called_with == {"admin_id": 999, "photo_file_id": "photo123", "caption": "سلام"}


@pytest.mark.asyncio
async def test_broadcast_worker_tallies_success_and_forbidden(monkeypatch):
    monkeypatch.setattr(users_repository, "get_all_active_chat_ids", AsyncMock(return_value=["c1", "c2", "c3"]))
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())
    monkeypatch.setattr(admin, "_BROADCAST_THROTTLE_SECONDS", 0)  # تست را سریع نگه می‌دارد

    async def fake_send_photo(chat_id, photo, caption=None):
        if chat_id == "c2":
            raise Forbidden("blocked")

    context = _context()
    context.bot.send_photo = AsyncMock(side_effect=fake_send_photo)

    await admin._broadcast_worker(context, admin_id=999, photo_file_id="p1", caption="سلام")

    assert context.bot.send_photo.await_count == 3
    admin_actions_repository.log_action.assert_awaited_once_with(
        999, "broadcast_sent", target="2 موفق / 1 ناموفق از 3"
    )
    context.bot.send_message.assert_awaited_once()
    summary_text = context.bot.send_message.await_args.kwargs["text"]
    assert "موفق: 2" in summary_text
    assert "ناموفق: 1" in summary_text


@pytest.mark.asyncio
async def test_broadcast_worker_still_notifies_admin_when_fetching_recipients_fails(monkeypatch):
    """اگر get_all_active_chat_ids خطای غیرمنتظره بدهد، ادمین باید همچنان
    پیام خلاصه را ببیند — رگرسیون مستقیم برای این رفع."""
    monkeypatch.setattr(
        users_repository, "get_all_active_chat_ids", AsyncMock(side_effect=RuntimeError("db locked"))
    )
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())
    monkeypatch.setattr(admin, "_BROADCAST_THROTTLE_SECONDS", 0)

    context = _context()

    await admin._broadcast_worker(context, admin_id=999, photo_file_id="p1", caption="سلام")

    context.bot.send_photo.assert_not_called()
    context.bot.send_message.assert_awaited_once()
    summary_text = context.bot.send_message.await_args.kwargs["text"]
    assert "موفق: 0" in summary_text
    assert "خطایی رخ داد" in summary_text


@pytest.mark.asyncio
async def test_broadcast_worker_still_notifies_admin_when_log_action_fails(monkeypatch):
    """admin_actions_repository.log_action عمداً خطا را قورت نمی‌دهد (طراحی
    خودش)؛ این نباید یعنی ادمین پیام خلاصه را نبیند."""
    monkeypatch.setattr(users_repository, "get_all_active_chat_ids", AsyncMock(return_value=["c1"]))
    monkeypatch.setattr(
        admin_actions_repository, "log_action", AsyncMock(side_effect=RuntimeError("db locked"))
    )
    monkeypatch.setattr(admin, "_BROADCAST_THROTTLE_SECONDS", 0)

    context = _context()

    await admin._broadcast_worker(context, admin_id=999, photo_file_id="p1", caption="سلام")

    context.bot.send_message.assert_awaited_once()
    summary_text = context.bot.send_message.await_args.kwargs["text"]
    assert "موفق: 1" in summary_text


# ============================== conversation_timeout ==============================
#
# نکته: اینجا خودِ رفتار زمان‌بندی واقعی JobQueue تست نمی‌شود (آن رفتار مال
# خودِ PTB است و جداگانه تست شده) — فقط دو چیزی که منطق اختصاصی ماست: (۱)
# conversation_timeout واقعاً روی هر دو ConversationHandler ست شده، (۲)
# هندلرهای TIMEOUT خودمان کاری که باید را انجام می‌دهند.

def test_user_search_conversation_has_timeout_configured():
    assert admin.user_search_conversation.conversation_timeout == admin._CONVERSATION_TIMEOUT_SECONDS
    assert ConversationHandler.TIMEOUT in admin.user_search_conversation.states


def test_broadcast_conversation_has_timeout_configured():
    assert admin.broadcast_conversation.conversation_timeout == admin._CONVERSATION_TIMEOUT_SECONDS
    assert ConversationHandler.TIMEOUT in admin.broadcast_conversation.states


@pytest.mark.asyncio
async def test_handle_search_timeout_notifies_the_chat():
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=999))
    context = _context()

    await admin.handle_search_timeout(update, context)

    context.bot.send_message.assert_awaited_once()
    assert context.bot.send_message.await_args.kwargs["chat_id"] == 999
    assert "زمان جستجو تمام شد" in context.bot.send_message.await_args.kwargs["text"]


@pytest.mark.asyncio
async def test_handle_broadcast_timeout_clears_pending_data_and_notifies():
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=999))
    context = _context(user_data={"broadcast_photo_file_id": "abc", "broadcast_caption": "سلام"})

    await admin.handle_broadcast_timeout(update, context)

    assert "broadcast_photo_file_id" not in context.user_data
    assert "broadcast_caption" not in context.user_data
    context.bot.send_message.assert_awaited_once()
    assert "لغو شد" in context.bot.send_message.await_args.kwargs["text"]


# ============================== محدودیت‌های قابل‌تنظیم ==============================

@pytest.mark.asyncio
async def test_admin_menu_limits_shows_current_values(monkeypatch):
    from bme_bot.db import feature_limits_repository

    monkeypatch.setattr(
        feature_limits_repository, "get_all_limits",
        AsyncMock(return_value=[
            {"feature_name": "quiz", "daily_limit": 5, "cooldown_seconds": 60, "unit": "count"},
            {"feature_name": "stt", "daily_limit": 300, "cooldown_seconds": 60, "unit": "seconds"},
        ]),
    )
    update, _, edits = _admin_update(callback_data="admin_menu:limits")
    context = _context()

    await admin.handle_admin_menu_callback(update, context)

    shown_text = edits[0][1]
    assert "5 بار در روز" in shown_text
    assert "5 دقیقه در روز" in shown_text  # ۳۰۰ ثانیه = ۵ دقیقه


@pytest.mark.asyncio
async def test_start_limit_edit_rejects_non_admin():
    update, _, _ = _admin_update(callback_data="admin_limits_edit:quiz", user_id=111)
    context = _context()

    result = await admin.start_limit_edit(update, context)

    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_start_limit_edit_prompts_with_current_count_value(monkeypatch):
    from bme_bot.db import feature_limits_repository

    monkeypatch.setattr(feature_limits_repository, "get_limit", AsyncMock(return_value=(5, 60, "count")))
    update, _, edits = _admin_update(callback_data="admin_limits_edit:quiz")
    context = _context()

    result = await admin.start_limit_edit(update, context)

    assert result == admin.LIMITS_AWAITING_VALUE
    assert context.user_data["editing_limit_feature"] == "quiz"
    assert "5 بار" in edits[0][1]


@pytest.mark.asyncio
async def test_start_limit_edit_prompts_in_minutes_for_seconds_unit(monkeypatch):
    """STT بر مبنای ثانیه ذخیره می‌شه ولی از ادمین به دقیقه پرسیده می‌شه
    (خواناتره) - ۳۰۰ ثانیه باید «۵ دقیقه» نشون داده بشه."""
    from bme_bot.db import feature_limits_repository

    monkeypatch.setattr(feature_limits_repository, "get_limit", AsyncMock(return_value=(300, 60, "seconds")))
    update, _, edits = _admin_update(callback_data="admin_limits_edit:stt")
    context = _context()

    result = await admin.start_limit_edit(update, context)

    assert result == admin.LIMITS_AWAITING_VALUE
    assert "5 دقیقه" in edits[0][1]
    assert "300" not in edits[0][1]  # نباید ثانیه‌ی خام رو نشون بده


@pytest.mark.asyncio
async def test_receive_limit_value_rejects_non_numeric():
    update, replies, _ = _admin_update(text="عدد نیست")
    context = _context(user_data={"editing_limit_feature": "quiz"})

    result = await admin.receive_limit_value(update, context)

    assert result == admin.LIMITS_AWAITING_VALUE
    assert any("عدد صحیح مثبت" in r for r in replies)


@pytest.mark.asyncio
async def test_receive_limit_value_rejects_zero_and_negative():
    update, replies, _ = _admin_update(text="0")
    context = _context(user_data={"editing_limit_feature": "quiz"})

    result = await admin.receive_limit_value(update, context)

    assert result == admin.LIMITS_AWAITING_VALUE


@pytest.mark.asyncio
async def test_receive_limit_value_saves_count_value_directly(monkeypatch):
    from bme_bot.db import feature_limits_repository

    monkeypatch.setattr(feature_limits_repository, "get_limit", AsyncMock(return_value=(5, 60, "count")))
    set_mock = AsyncMock()
    monkeypatch.setattr(feature_limits_repository, "set_daily_limit", set_mock)
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())

    update, replies, _ = _admin_update(text="2")
    context = _context(user_data={"editing_limit_feature": "quiz"})

    result = await admin.receive_limit_value(update, context)

    assert result == ConversationHandler.END
    set_mock.assert_awaited_once_with("quiz", 2)
    assert any("2" in r and "بار در روز" in r for r in replies)


@pytest.mark.asyncio
async def test_receive_limit_value_converts_minutes_to_seconds_for_stt(monkeypatch):
    """عددی که ادمین برای STT می‌فرسته دقیقه‌ست - باید قبل از ذخیره در ۶۰
    ضرب بشه."""
    from bme_bot.db import feature_limits_repository

    monkeypatch.setattr(feature_limits_repository, "get_limit", AsyncMock(return_value=(300, 60, "seconds")))
    set_mock = AsyncMock()
    monkeypatch.setattr(feature_limits_repository, "set_daily_limit", set_mock)
    monkeypatch.setattr(admin_actions_repository, "log_action", AsyncMock())

    update, replies, _ = _admin_update(text="10")  # ۱۰ دقیقه
    context = _context(user_data={"editing_limit_feature": "stt"})

    result = await admin.receive_limit_value(update, context)

    assert result == ConversationHandler.END
    set_mock.assert_awaited_once_with("stt", 600)  # ۱۰ دقیقه = ۶۰۰ ثانیه
    assert any("دقیقه در روز" in r for r in replies)


@pytest.mark.asyncio
async def test_receive_limit_value_clears_editing_state():
    from bme_bot.db import feature_limits_repository

    async def _fake_get_limit(name):
        return (5, 60, "count")

    import unittest.mock as mock_module

    with mock_module.patch.object(feature_limits_repository, "get_limit", side_effect=_fake_get_limit), \
         mock_module.patch.object(feature_limits_repository, "set_daily_limit", AsyncMock()), \
         mock_module.patch.object(admin_actions_repository, "log_action", AsyncMock()):
        update, _, _ = _admin_update(text="3")
        context = _context(user_data={"editing_limit_feature": "quiz"})

        await admin.receive_limit_value(update, context)

        assert "editing_limit_feature" not in context.user_data


@pytest.mark.asyncio
async def test_cancel_limit_edit_clears_state_and_confirms():
    update, replies, _ = _admin_update(text="/cancel")
    context = _context(user_data={"editing_limit_feature": "quiz"})

    result = await admin.cancel_limit_edit(update, context)

    assert result == ConversationHandler.END
    assert "editing_limit_feature" not in context.user_data
    assert replies == ["ویرایش محدودیت لغو شد."]


@pytest.mark.asyncio
async def test_handle_limits_edit_timeout_clears_state_and_notifies():
    update = SimpleNamespace(effective_chat=SimpleNamespace(id=999))
    context = _context(user_data={"editing_limit_feature": "quiz"})

    await admin.handle_limits_edit_timeout(update, context)

    assert "editing_limit_feature" not in context.user_data
    context.bot.send_message.assert_awaited_once()
    assert "لغو شد" in context.bot.send_message.await_args.kwargs["text"]


def test_limits_edit_conversation_uses_shared_timeout():
    assert admin.limits_edit_conversation.conversation_timeout == admin._CONVERSATION_TIMEOUT_SECONDS


def test_limits_edit_pattern_only_matches_known_features():
    """رگرسیون‌گارد: callback_data باید فقط برای پنج فیچر شناخته‌شده match
    بشه - یه اسم دلبخواه نباید وارد ConversationHandler بشه."""
    import re

    entry_point = admin.limits_edit_conversation.entry_points[0]
    assert re.match(entry_point.pattern, "admin_limits_edit:quiz")
    assert re.match(entry_point.pattern, "admin_limits_edit:stt")
    assert not re.match(entry_point.pattern, "admin_limits_edit:not_a_real_feature")
