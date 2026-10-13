# tests/test_config_paths.py
#
# رجوع به کامنت بالای USERS_DB_PATH در config.py: قبلاً پیش‌فرض این مسیرها
# صرفاً یه نام فایل نسبی بود، وابسته به CWD لحظه‌ی اجرای پردازه، نه به
# ریشه‌ی پروژه — یعنی یه اجرای غیرمعمول (cron، systemd با WorkingDirectory
# متفاوت) می‌تونست بی‌سروصدا یه DB خالی در مسیر غلط بسازه. این تست همون
# invariant رو برای همیشه قفل می‌کنه: این مسیرها همیشه باید مطلق باشن.

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402


def test_db_and_archive_paths_default_to_absolute():
    assert os.path.isabs(config.USERS_DB_PATH)
    assert os.path.isabs(config.EQUIPMENT_DB_PATH)
    assert os.path.isabs(config.QUIZ_ARCHIVE_PATH)


def test_db_and_archive_paths_are_anchored_to_base_dir_not_cwd():
    """مهم‌ترین قسمت تست: صرفاً مطلق‌بودن کافی نیست (os.path.abspath('x')
    هم مطلقه، ولی باز به CWD وابسته‌ست) — باید دقیقاً زیرِ BASE_DIR
    (ریشه‌ی واقعی پروژه، مستقل از CWD) باشن."""
    assert config.USERS_DB_PATH == os.path.join(config.BASE_DIR, "users.db")
    assert config.EQUIPMENT_DB_PATH == os.path.join(config.BASE_DIR, "medical_device.db")
    assert config.QUIZ_ARCHIVE_PATH == os.path.join(config.BASE_DIR, "quiz_archive.jsonl")


def test_log_and_data_dir_were_already_absolute_consistency_check():
    """این دوتا از قبل درست بودن (الگویی که بقیه باید ازش پیروی کنن) —
    این تست فقط تایید می‌کنه که الگوی مرجع هنوز سرجاشه."""
    assert os.path.isabs(config.LOG_DIR)
    assert os.path.isabs(config.DATA_DIR)
