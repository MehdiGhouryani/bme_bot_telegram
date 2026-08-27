# tests/test_admin_actions_repository.py
#
# تست لاگ اقدامات ادمین (بن/آنبن، Broadcast) — این محافظت در برابر خطای
# انسانی است، پس برخلاف feature_usage، خطای ثبت اینجا نباید بی‌صدا قورت
# داده شود (تست جداگانه‌اش پایین‌تر).

import sys
from pathlib import Path

import pytest
import pytest_asyncio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import admin_actions_repository, app_connection  # noqa: E402


@pytest_asyncio.fixture
async def temp_users_db(tmp_path, monkeypatch):
    db_path = tmp_path / "users_test.db"
    monkeypatch.setattr(config, "USERS_DB_PATH", str(db_path))
    await app_connection.setup_users_database()
    return db_path


@pytest.mark.asyncio
async def test_log_action_then_get_recent_actions(temp_users_db):
    await admin_actions_repository.log_action(111, "ban_user", target="42")
    await admin_actions_repository.log_action(111, "broadcast_sent", target="120 users")

    actions = await admin_actions_repository.get_recent_actions()

    assert len(actions) == 2
    assert actions[0]["action"] == "broadcast_sent"  # جدیدترین اول
    assert actions[1]["action"] == "ban_user"
    assert actions[1]["target"] == "42"
    assert actions[1]["admin_id"] == 111


@pytest.mark.asyncio
async def test_get_recent_actions_respects_limit(temp_users_db):
    for i in range(5):
        await admin_actions_repository.log_action(111, f"action_{i}")

    actions = await admin_actions_repository.get_recent_actions(limit=2)

    assert len(actions) == 2
    assert actions[0]["action"] == "action_4"  # جدیدترین اول


@pytest.mark.asyncio
async def test_get_recent_actions_empty_when_none_logged(temp_users_db):
    assert await admin_actions_repository.get_recent_actions() == []


@pytest.mark.asyncio
async def test_log_action_propagates_real_errors(monkeypatch, tmp_path):
    """برخلاف feature_usage_repository.log_usage، این تابع عمداً خطا را قورت
    نمی‌دهد — یک اقدام حساس که ثبت نشده باید قابل‌توجه باشد، نه بی‌صدا گم شود."""
    monkeypatch.setattr(config, "USERS_DB_PATH", str(tmp_path / "no" / "such" / "dir" / "db.sqlite"))

    with pytest.raises(Exception):
        await admin_actions_repository.log_action(111, "ban_user", target="42")
