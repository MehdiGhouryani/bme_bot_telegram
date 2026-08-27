# tests/test_logging_setup.py
#
# تست _TruncatingRotatingFileHandler با I/O واقعی روی فایل (نه mock) — چون
# دقیقاً همین جزئیات (doRollover با backupCount=0 در پیاده‌سازی استاندارد
# پایتون اصلاً کاری نمی‌کند) چیزیه که باید واقعاً تضمین بشه، نه فقط فرض
# بشه.

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.logging_setup import _TruncatingRotatingFileHandler  # noqa: E402


def test_file_never_exceeds_max_bytes_after_many_writes(tmp_path):
    log_path = tmp_path / "test.log"
    # maxBytes کوچک عمداً برای تست سریع - رفتار doRollover مستقل از عدد است.
    handler = _TruncatingRotatingFileHandler(
        filename=str(log_path), maxBytes=500, backupCount=0, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("test_truncating_handler")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    try:
        for i in range(200):
            logger.info("این یک خط لاگ تستی نسبتاً بلند است شماره %d برای پر کردن فایل", i)
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert log_path.exists()
    assert log_path.stat().st_size <= 500 + 300  # کمی حاشیه برای آخرین خط قبل از rollover


def test_no_backup_files_are_ever_created(tmp_path):
    """چون backupCount=0 و doRollover واقعاً truncate می‌کند (نه rename)،
    نباید هیچ‌وقت test.log.1 یا مشابهش ساخته بشه."""
    log_path = tmp_path / "test.log"
    handler = _TruncatingRotatingFileHandler(
        filename=str(log_path), maxBytes=200, backupCount=0, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("test_truncating_handler_backups")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    try:
        for i in range(100):
            logger.info("خط شماره %d " + ("پ" * 20), i)
    finally:
        logger.removeHandler(handler)
        handler.close()

    backup_files = list(tmp_path.glob("test.log.*"))
    assert backup_files == []


def test_file_content_after_rollover_is_not_unbounded_history(tmp_path):
    """بعد از چندین rollover، محتوای فایل فقط شامل نوشته‌های *اخیر* باشه،
    نه هرچی از اول لاگ شده (یعنی truncate واقعاً اتفاق افتاده)."""
    log_path = tmp_path / "test.log"
    handler = _TruncatingRotatingFileHandler(
        filename=str(log_path), maxBytes=300, backupCount=0, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("test_truncating_handler_content")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    try:
        for i in range(50):
            logger.info("MARKER_%d_" + ("x" * 20), i)
    finally:
        logger.removeHandler(handler)
        handler.close()

    content = log_path.read_text(encoding="utf-8")
    assert "MARKER_0_" not in content  # اولین نوشته‌ها باید حذف شده باشن
    assert "MARKER_49_" in content or "MARKER_4" in content  # آخری‌ها مونده باشن


def test_max_bytes_constant_is_ten_megabytes():
    from bme_bot import logging_setup

    assert logging_setup._MAX_BYTES_PER_FILE == 10 * 1024 * 1024
