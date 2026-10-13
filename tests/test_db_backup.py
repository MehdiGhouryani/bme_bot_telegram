# tests/test_db_backup.py

import datetime
import gzip
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.utils import admin as admin_utils  # noqa: E402
from bme_bot.utils import db_backup  # noqa: E402


def _make_db(path, rows=3, wal=False):
    conn = sqlite3.connect(path)
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany("INSERT INTO users VALUES (?, ?)", [(i, f"u{i}") for i in range(rows)])
    conn.commit()
    return conn


def _restore(gz_path, tmp_path):
    out = tmp_path / "restored.db"
    with gzip.open(gz_path, "rb") as f_in, open(out, "wb") as f_out:
        f_out.write(f_in.read())
    conn = sqlite3.connect(out)
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def test_create_backup_produces_restorable_gz(tmp_path):
    src = tmp_path / "users.db"
    _make_db(str(src), rows=5).close()

    path = db_backup.create_backup(str(src), str(tmp_path / "bk"), keep=4)

    assert path.endswith(".db.gz")
    assert os.path.basename(path).startswith("users-")
    assert _restore(path, tmp_path) == 5


def test_backup_includes_uncheckpointed_wal_data_while_source_connection_open(tmp_path):
    """مهم‌ترین دلیل استفاده از backup API: داده‌ای که هنوز فقط در -wal است."""
    src = tmp_path / "users.db"
    conn = _make_db(str(src), rows=4, wal=True)  # اتصال باز می‌ماند
    try:
        assert (tmp_path / "users.db-wal").exists()
        path = db_backup.create_backup(str(src), str(tmp_path / "bk"), keep=4)
    finally:
        conn.close()

    assert _restore(path, tmp_path) == 4


def test_create_backup_missing_source_raises_and_leaves_no_files(tmp_path):
    dest = tmp_path / "bk"
    with pytest.raises(FileNotFoundError):
        db_backup.create_backup(str(tmp_path / "nope.db"), str(dest), keep=4)
    assert not dest.exists() or list(dest.iterdir()) == []


def test_create_backup_cleans_temp_files(tmp_path):
    src = tmp_path / "users.db"
    _make_db(str(src)).close()
    dest = tmp_path / "bk"

    db_backup.create_backup(str(src), str(dest), keep=4)

    assert [p.name for p in dest.iterdir() if p.name.startswith(".") or p.name.endswith(".tmp")] == []


def test_rotation_keeps_only_newest_n(tmp_path):
    src = tmp_path / "users.db"
    _make_db(str(src)).close()
    dest = tmp_path / "bk"
    base = datetime.datetime(2026, 10, 1, 3, 0, 0)

    paths = [
        db_backup.create_backup(str(src), str(dest), keep=3, now=base + datetime.timedelta(days=7 * i))
        for i in range(5)
    ]

    remaining = sorted(os.listdir(dest))
    assert remaining == sorted(os.path.basename(p) for p in paths[-3:])


def test_rotation_ignores_unrelated_files(tmp_path):
    src = tmp_path / "users.db"
    _make_db(str(src)).close()
    dest = tmp_path / "bk"
    dest.mkdir()
    (dest / "notes.txt").write_text("keep me")

    for i in range(3):
        db_backup.create_backup(
            str(src), str(dest), keep=1, now=datetime.datetime(2026, 10, 1 + i, 3, 0, 0),
        )

    assert (dest / "notes.txt").exists()
    assert len([n for n in os.listdir(dest) if n.endswith(".db.gz")]) == 1


# --------------------------- run_weekly_backup ---------------------------

def _context():
    return SimpleNamespace(bot=SimpleNamespace(send_document=AsyncMock(), send_message=AsyncMock()))


@pytest.fixture
def backup_env(tmp_path, monkeypatch):
    src = tmp_path / "users.db"
    _make_db(str(src), rows=2).close()
    monkeypatch.setattr(config, "USERS_DB_PATH", str(src))
    monkeypatch.setattr(config, "BACKUP_DIR", str(tmp_path / "bk"))
    monkeypatch.setattr(config, "BACKUP_KEEP", 4)
    monkeypatch.setattr(config, "BACKUP_ENABLED", True)
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["111", "222"])
    monkeypatch.setattr(admin_utils, "_dynamic_admin_ids", {"333"})
    return tmp_path


@pytest.mark.asyncio
async def test_run_weekly_backup_sends_document_to_every_admin(backup_env):
    ctx = _context()

    await db_backup.run_weekly_backup(ctx)

    sent = ctx.bot.send_document.await_args_list
    assert [c.kwargs["chat_id"] for c in sent] == ["111", "222", "333"]
    first = sent[0].kwargs
    assert first["filename"].endswith(".db.gz")
    assert "users.db" in first["caption"]
    # محتوای ارسالی واقعاً یک gzip سالم است
    assert gzip.decompress(first["document"]).startswith(b"SQLite format 3")


@pytest.mark.asyncio
async def test_run_weekly_backup_one_admin_failure_does_not_stop_others(backup_env):
    ctx = _context()
    ctx.bot.send_document = AsyncMock(side_effect=[Exception("blocked"), None, None])

    await db_backup.run_weekly_backup(ctx)

    assert ctx.bot.send_document.await_count == 3


@pytest.mark.asyncio
async def test_run_weekly_backup_disabled_does_nothing(backup_env, monkeypatch):
    monkeypatch.setattr(config, "BACKUP_ENABLED", False)
    ctx = _context()

    await db_backup.run_weekly_backup(ctx)

    ctx.bot.send_document.assert_not_called()
    assert not (backup_env / "bk").exists()


@pytest.mark.asyncio
async def test_run_weekly_backup_failure_alerts_admins_and_does_not_raise(backup_env, monkeypatch):
    monkeypatch.setattr(config, "USERS_DB_PATH", str(backup_env / "missing.db"))
    ctx = _context()

    await db_backup.run_weekly_backup(ctx)  # نباید exception بدهد

    ctx.bot.send_document.assert_not_called()
    texts = [c.kwargs["text"] for c in ctx.bot.send_message.await_args_list]
    assert texts and all("ناموفق" in t for t in texts)
    assert "FileNotFoundError" in texts[0]


@pytest.mark.asyncio
async def test_run_weekly_backup_too_large_keeps_local_and_notifies(backup_env, monkeypatch):
    monkeypatch.setattr(db_backup, "_MAX_TELEGRAM_FILE_BYTES", 10)
    ctx = _context()

    await db_backup.run_weekly_backup(ctx)

    ctx.bot.send_document.assert_not_called()
    assert any("بزرگ" in c.kwargs["text"] for c in ctx.bot.send_message.await_args_list)
    assert len(list((backup_env / "bk").glob("users-*.db.gz"))) == 1


def test_get_all_admin_ids_dedups_and_merges(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["1", "2"])
    monkeypatch.setattr(admin_utils, "_dynamic_admin_ids", {"2"})
    assert admin_utils.get_all_admin_ids() == ["1", "2"]
