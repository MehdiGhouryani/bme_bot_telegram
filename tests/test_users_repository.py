# tests/test_users_repository.py
#
# تست‌های users_repository.py. save_user منطق غیربدیهی دارد (رفع باگ واقعی
# INSERT OR REPLACE که is_banned/joined_at را پاک می‌کرد — جزئیات در خودِ
# db/users_repository.py)، پس تست مستقیم آن اینجا لازم است.
#
# برخلاف test_ai_usage_repository.py (که جدول را دستی با SQL خام می‌ساخت)،
# اینجا از خودِ app_connection.setup_users_database() استفاده می‌شود — چون
# users_repository به چند جدول/ستون هم‌زمان وابسته است و ساخت دستی مصنوعی
# ریسک واگرایی از schema واقعی دارد.

import sys
from pathlib import Path

import pytest
import pytest_asyncio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import app_connection, users_repository  # noqa: E402


@pytest_asyncio.fixture
async def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    await app_connection.setup_users_database()
    return db_path


@pytest.mark.asyncio
async def test_save_user_creates_row_with_joined_at(temp_users_db):
    await users_repository.save_user(111, "alice", "chat-111")

    users = await users_repository.search_user("111")
    assert len(users) == 1
    assert users[0]["username"] == "alice"
    assert users[0]["joined_at"] is not None
    assert users[0]["is_banned"] == 0


@pytest.mark.asyncio
async def test_save_user_does_not_reset_ban_on_repeat_call(temp_users_db):
    """رگرسیون مستقیم باگ کشف‌شده: قبلاً INSERT OR REPLACE یعنی یک کاربر
    بن‌شده با زدن دوباره‌ی /start (که save_user را دوباره صدا می‌زند) بی‌صدا
    آنبن می‌شد. این تست دقیقاً همین سناریو را شبیه‌سازی می‌کند."""
    await users_repository.save_user(222, "bob", "chat-222")
    await users_repository.set_banned(222, True)

    assert await users_repository.is_banned(222) is True

    # کاربر دوباره /start می‌زند (مثلاً بعد از ترک و بازگشت به ربات)
    await users_repository.save_user(222, "bob", "chat-222-new")

    assert await users_repository.is_banned(222) is True  # باید همچنان بن باشد


@pytest.mark.asyncio
async def test_save_user_does_not_reset_joined_at_on_repeat_call(temp_users_db):
    await users_repository.save_user(333, "carol", "chat-333")
    first = (await users_repository.search_user("333"))[0]["joined_at"]

    await users_repository.save_user(333, "carol_new_username", "chat-333")
    second = (await users_repository.search_user("333"))[0]["joined_at"]

    assert first == second  # joined_at نباید با فراخوانی دوم عوض شود
    assert (await users_repository.search_user("333"))[0]["username"] == "carol_new_username"


@pytest.mark.asyncio
async def test_touch_last_seen_creates_row_for_unknown_user(temp_users_db):
    """کاربری که هرگز /start نزده (مثلاً مستقیم از /ask استفاده کرده) باید
    بعد از اولین تعامل هم در آمار «فعال» دیده شود."""
    await users_repository.touch_last_seen(999)

    users = await users_repository.search_user("999")
    assert len(users) == 1
    assert users[0]["last_seen_at"] is not None
    assert users[0]["is_banned"] == 0  # کاربر ناشناس مسدود نیست


@pytest.mark.asyncio
async def test_touch_last_seen_does_not_reset_ban(temp_users_db):
    await users_repository.save_user(444, "dave", "chat-444")
    await users_repository.set_banned(444, True)

    await users_repository.touch_last_seen(444)

    assert await users_repository.is_banned(444) is True


@pytest.mark.asyncio
async def test_is_banned_false_for_nonexistent_user(temp_users_db):
    assert await users_repository.is_banned(123456) is False


@pytest.mark.asyncio
async def test_set_banned_then_unban(temp_users_db):
    await users_repository.save_user(555, "eve", "chat-555")
    await users_repository.set_banned(555, True)
    assert await users_repository.is_banned(555) is True

    await users_repository.set_banned(555, False)
    assert await users_repository.is_banned(555) is False


@pytest.mark.asyncio
async def test_search_user_by_exact_id(temp_users_db):
    await users_repository.save_user(666, "frank", "chat-666")
    await users_repository.save_user(667, "frankie", "chat-667")

    results = await users_repository.search_user("666")
    assert len(results) == 1
    assert results[0]["user_id"] == 666


@pytest.mark.asyncio
async def test_search_user_by_partial_username(temp_users_db):
    await users_repository.save_user(701, "grace_bme", "chat-701")
    await users_repository.save_user(702, "grace_admin", "chat-702")
    await users_repository.save_user(703, "someone_else", "chat-703")

    results = await users_repository.search_user("grace")
    usernames = {r["username"] for r in results}
    assert usernames == {"grace_bme", "grace_admin"}


@pytest.mark.asyncio
async def test_search_user_no_match_returns_empty_list(temp_users_db):
    results = await users_repository.search_user("no_such_user")
    assert results == []


@pytest.mark.asyncio
async def test_get_user_stats_counts_total_and_banned(temp_users_db):
    await users_repository.save_user(801, "u1", "c1")
    await users_repository.save_user(802, "u2", "c2")
    await users_repository.save_user(803, "u3", "c3")
    await users_repository.set_banned(802, True)

    stats = await users_repository.get_user_stats()

    assert stats["total"] == 3
    assert stats["banned"] == 1
    assert stats["new_today"] == 3  # هرسه همین الان ساخته شدند


@pytest.mark.asyncio
async def test_stored_timestamp_format_is_sqlite_comparable(temp_users_db):
    """رگرسیون: اگر _now_iso() فرمت ISO پایتون تولید کند (با 'T' و پسوند
    timezone، مثل "2026-08-09T10:17:53.956565+00:00")، با خروجی SQLite
    datetime() ("2026-08-09 10:17:53") به‌درستی مقایسه نمی‌شود — چون 'T' در
    ASCII از فاصله بزرگ‌تر است، یک رکورد «همین‌الان» حتی در برابر یک
    آستانه‌ی «یک ساعت در آینده» هم اشتباهاً True می‌شود (تایید‌شده مستقیم
    روی SQLite واقعی). این یعنی همه‌ی فیلترهای «N روز اخیر»
    (get_user_stats/send_daily_summary/سلامت سیستم) روی مرز هر روز نادقیق
    می‌شوند. این تست دقیقاً همان سناریو را بازتولید می‌کند."""
    await users_repository.touch_last_seen(555)

    async with app_connection.get_connection() as conn:
        async with conn.execute(
            "SELECT COUNT(*) FROM users WHERE user_id = 555 "
            "AND last_seen_at >= datetime('now', '+1 hour')"
        ) as cursor:
            row = await cursor.fetchone()

    assert row[0] == 0, (
        "کاربری که همین الان last_seen_at شده نباید با آستانه‌ی «یک ساعت در "
        "آینده» match شود — اگر ۱ باشد یعنی فرمت timestamp با مقایسه‌ی "
        "SQLite datetime() دوباره ناسازگار شده."
    )


@pytest.mark.asyncio
async def test_get_all_active_chat_ids_excludes_banned(temp_users_db):
    await users_repository.save_user(1001, "u1", "chat-1001")
    await users_repository.save_user(1002, "u2", "chat-1002")
    await users_repository.save_user(1003, "u3", "chat-1003")
    await users_repository.set_banned(1002, True)

    chat_ids = await users_repository.get_all_active_chat_ids()

    assert set(chat_ids) == {"chat-1001", "chat-1003"}


@pytest.mark.asyncio
async def test_get_user_stats_active_reflects_last_seen(temp_users_db):
    await users_repository.save_user(901, "active_user", "c1")
    await users_repository.touch_last_seen(901)

    stats = await users_repository.get_user_stats()

    assert stats["active_7d"] >= 1
    assert stats["active_30d"] >= 1
