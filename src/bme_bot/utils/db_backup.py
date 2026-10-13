# src/bme_bot/utils/db_backup.py
#
# بکاپ خودکار هفتگی users.db.
#
# چرا SQLite backup API و نه کپی ساده‌ی فایل؟ users.db در حالت WAL است
# (db/_connection_factory.py): بخشی از داده‌های تازه ممکن است فقط در فایل
# -wal باشد و کپی خام .db در حین کار بات، نسخه‌ی ناقص/ناسازگار می‌دهد.
# sqlite3.Connection.backup یک snapshot سازگار می‌گیرد، حتی وقتی بات
# هم‌زمان می‌نویسد.
#
# جریان: backup API → فایل موقت → integrity_check → gzip → جابه‌جایی اتمی به
# users-YYYYmmdd-HHMMSS.db.gz → حذف نسخه‌های قدیمی‌تر از BACKUP_KEEP.
# کار سنگین (sync) داخل asyncio.to_thread اجرا می‌شود تا event loop بلاک نشود.
#
# ارسال به ادمین‌ها best-effort است: شکست یک ادمین بقیه را متوقف نمی‌کند و
# هیچ خطایی از job بیرون نمی‌زند (فقط لاگ + اطلاع به ادمین‌ها). فایل شامل
# شناسه‌ی کاربران است، پس *فقط* به چت خصوصی ادمین‌ها می‌رود، نه گروه.
#
# بازگردانی عمداً دستی است: بات را خاموش کن، فایل را gunzip کن و جای users.db
# بگذار (و -wal/-shm قدیمی را پاک کن).

import asyncio
import datetime
import glob
import gzip
import logging
import os
import shutil
import sqlite3

from telegram.ext import ContextTypes

from .. import config
from . import admin as admin_utils

logger = logging.getLogger(__name__)

_BACKUP_PREFIX = "users-"
_BACKUP_SUFFIX = ".db.gz"
# سقف رسمی آپلود فایل توسط بات ۵۰MB است؛ کمی حاشیه‌ی امن.
_MAX_TELEGRAM_FILE_BYTES = 49 * 1024 * 1024


def create_backup(src_path: str, dest_dir: str, keep: int, now: datetime.datetime | None = None) -> str:
    """(sync) از src_path یک بکاپ فشرده در dest_dir می‌سازد، قدیمی‌ها را
    می‌چرخاند و مسیر فایل نهایی را برمی‌گرداند. روی هر مشکل exception می‌دهد
    و فایل موقت را پاک می‌کند."""
    if not os.path.isfile(src_path):
        raise FileNotFoundError(f"دیتابیس برای بکاپ پیدا نشد: {src_path}")

    now = now or datetime.datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    os.makedirs(dest_dir, exist_ok=True)

    tmp_db = os.path.join(dest_dir, f".{_BACKUP_PREFIX}{stamp}.tmp.db")
    final_path = os.path.join(dest_dir, f"{_BACKUP_PREFIX}{stamp}{_BACKUP_SUFFIX}")
    tmp_gz = final_path + ".tmp"

    try:
        src = sqlite3.connect(src_path, timeout=30)
        try:
            dst = sqlite3.connect(tmp_db)
            try:
                src.backup(dst)
                result = dst.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise RuntimeError(f"integrity_check بکاپ ناموفق بود: {result}")
            finally:
                dst.close()
        finally:
            src.close()

        with open(tmp_db, "rb") as f_in, gzip.open(tmp_gz, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.replace(tmp_gz, final_path)
    finally:
        for leftover in (tmp_db, tmp_gz):
            try:
                os.remove(leftover)
            except FileNotFoundError:
                pass

    _rotate(dest_dir, keep)
    return final_path


def _rotate(dest_dir: str, keep: int) -> None:
    """فقط فایل‌های هم‌الگوی users-*.db.gz را می‌چرخاند؛ نام شامل timestamp
    است، پس مرتب‌سازی نامی = مرتب‌سازی زمانی."""
    files = sorted(glob.glob(os.path.join(dest_dir, f"{_BACKUP_PREFIX}*{_BACKUP_SUFFIX}")), reverse=True)
    for old in files[max(1, keep):]:
        try:
            os.remove(old)
        except OSError as e:
            logger.warning("could not remove old backup %s: %s", old, e)


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


async def run_weekly_backup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """callback مربوط به job هفتگی (app._post_init). فقط context.bot لازم دارد."""
    if not config.BACKUP_ENABLED:
        return

    try:
        path = await asyncio.to_thread(
            create_backup, config.USERS_DB_PATH, config.BACKUP_DIR, config.BACKUP_KEEP,
        )
    except Exception as e:
        logger.exception("weekly users.db backup failed")
        await admin_utils.notify_admins(
            context, f"⚠️ بکاپ هفتگی users.db ناموفق بود: {type(e).__name__}",
        )
        return

    size = os.path.getsize(path)
    if size > _MAX_TELEGRAM_FILE_BYTES:
        logger.warning("backup %s is %d bytes, too large for Telegram upload", path, size)
        await admin_utils.notify_admins(
            context,
            f"⚠️ بکاپ هفتگی users.db ساخته شد ({_format_size(size)}) ولی برای ارسال در "
            f"تلگرام بزرگ است. فقط روی سرور نگه داشته شد: {os.path.basename(path)}",
        )
        return

    admin_ids = admin_utils.get_all_admin_ids()
    if not admin_ids:
        logger.warning("backup created but no admin to send it to: %s", path)
        return

    data = await asyncio.to_thread(lambda: open(path, "rb").read())
    caption = (
        "🗄 بکاپ هفتگی users.db\n"
        f"📅 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"📦 {_format_size(size)}"
    )
    for admin_id in admin_ids:
        try:
            await context.bot.send_document(
                chat_id=admin_id, document=data, filename=os.path.basename(path), caption=caption,
            )
        except Exception as e:
            logger.error("failed to send backup to admin %s: %s", admin_id, e)
