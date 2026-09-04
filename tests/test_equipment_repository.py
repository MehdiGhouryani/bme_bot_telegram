# tests/test_equipment_repository.py
#
# این تست همان رگرسیونی است که برای رفع باگ SQL injection در
# equipment_repository.py لازم است: اثبات اینکه allow-list واقعاً جلوی
# تزریق نام ستون دلخواه را می‌گیرد — نه فقط در تئوری، بلکه با یک دیتابیس
# واقعی موقت.

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import equipment_repository  # noqa: E402


@pytest.fixture
def temp_equipment_db(tmp_path, monkeypatch):
    db_path = tmp_path / "medical_device_test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE information (
            name TEXT PRIMARY KEY,
            definition TEXT,
            photo TEXT,
            types TEXT,
            structure TEXT,
            operation TEXT,
            related_technologies TEXT,
            advantages_disadvantages TEXT,
            safety TEXT,
            secret_admin_column TEXT
        )"""
    )
    conn.execute(
        "INSERT INTO information VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "xray", "تعریف اشعه ایکس", "photo_file_id", "انواع اشعه ایکس",
            "ساختار دستگاه", "نحوه عملکرد", "تکنولوژی مشابه", "مزایا و معایب",
            "نکات ایمنی", "TOP SECRET - should never leak",
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(config, "EQUIPMENT_DB_PATH", str(db_path))
    return db_path


@pytest.mark.asyncio
async def test_valid_action_returns_correct_text(temp_equipment_db):
    result = await equipment_repository.get_action_text("xray", "structure")
    assert result == "ساختار دستگاه"


@pytest.mark.asyncio
async def test_all_seven_allowed_actions_work(temp_equipment_db):
    for action in equipment_repository.ALLOWED_ACTIONS:
        result = await equipment_repository.get_action_text("xray", action)
        assert result is not None


@pytest.mark.asyncio
async def test_unlisted_column_is_rejected_even_if_it_exists_in_the_table(temp_equipment_db):
    """ستونی که واقعاً در جدول وجود دارد ولی در allow-list نیست (مثلاً یک ستون
    داخلی/حساس) نباید هرگز از طریق این تابع قابل خواندن باشد."""
    result = await equipment_repository.get_action_text("xray", "secret_admin_column")
    assert result is None


@pytest.mark.asyncio
async def test_sql_injection_attempt_via_callback_data_is_blocked(temp_equipment_db):
    """سناریوی حمله: یک کلاینت تلگرام دستکاری‌شده، مقداری
    غیر از دکمه‌های واقعی ربات در callback_data می‌فرستد. باید بدون خطا و بدون
    اجرای کوئری، None برگردد."""
    malicious_actions = [
        "name; DROP TABLE information;--",
        "definition, photo",
        "*",
        "(SELECT sqlite_version())",
        "structure -- comment",
    ]
    for action in malicious_actions:
        result = await equipment_repository.get_action_text("xray", action)
        assert result is None

    # مهم‌تر از همه: جدول هنوز باید سالم و دست‌نخورده باشد
    result_after = await equipment_repository.get_action_text("xray", "structure")
    assert result_after == "ساختار دستگاه"


@pytest.mark.asyncio
async def test_definition_with_photo_uses_fixed_columns_not_user_input(temp_equipment_db):
    result = await equipment_repository.get_definition_with_photo("xray")
    assert result == ("تعریف اشعه ایکس", "photo_file_id")


@pytest.mark.asyncio
async def test_missing_device_returns_none(temp_equipment_db):
    result = await equipment_repository.get_action_text("nonexistent_device", "structure")
    assert result is None


# --- update_action_text (دکمه‌ی ویرایش ادمین) ---

@pytest.mark.asyncio
async def test_update_action_text_creates_row_when_device_has_none_yet(tmp_path, monkeypatch):
    """رگرسیون: قبلاً این تابع فقط UPDATE می‌زد — اگه ردیف device اصلاً
    وجود نداشت، بی‌سروصدا ۰ ردیف تغییر می‌کرد و متن هیچ‌وقت ذخیره نمی‌شد،
    درحالی‌که فراخواننده (equipment_admin_edit.py) فکر می‌کرد ذخیره موفق
    بوده. الان باید upsert باشه: هم دستگاه هم مقدار ستون رو بسازه."""
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE information (
            name TEXT PRIMARY KEY, definition TEXT, photo TEXT, types TEXT, structure TEXT,
            operation TEXT, related_technologies TEXT, advantages_disadvantages TEXT, safety TEXT
        )"""
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "EQUIPMENT_DB_PATH", str(db_path))

    # قبل از هر ویرایشی، دستگاه اصلاً وجود نداره
    assert await equipment_repository.get_action_text("new_device", "types") is None

    await equipment_repository.update_action_text("new_device", "types", "انواع تازه")

    assert await equipment_repository.get_action_text("new_device", "types") == "انواع تازه"
    raw = sqlite3.connect(db_path).execute(
        "SELECT COUNT(*) FROM information WHERE name = ?", ("new_device",)
    ).fetchone()[0]
    assert raw == 1  # دقیقاً یک ردیف ساخته شد، نه صفر و نه بیشتر


@pytest.mark.asyncio
async def test_update_action_text_fills_previously_empty_column_on_existing_device(temp_equipment_db):
    """همون سناریو، ولی برای دستگاهی که از قبل وجود داره ولی یه ستونش هنوز
    NULL/خالیه — باید بشه اون یکی رو هم بدون تاثیر روی بقیه‌ی ستون‌ها پر کرد."""
    conn = sqlite3.connect(temp_equipment_db)
    conn.execute("UPDATE information SET safety = NULL WHERE name = 'xray'")
    conn.commit()
    conn.close()
    assert await equipment_repository.get_action_text("xray", "safety") is None

    await equipment_repository.update_action_text("xray", "safety", "نکات ایمنی تازه")

    assert await equipment_repository.get_action_text("xray", "safety") == "نکات ایمنی تازه"
    # بقیه‌ی ستون‌های همون دستگاه نباید دست‌خورده باشن
    assert await equipment_repository.get_action_text("xray", "definition") == "تعریف اشعه ایکس"


@pytest.mark.asyncio
async def test_update_action_text_changes_stored_value(temp_equipment_db):
    await equipment_repository.update_action_text("xray", "structure", "ساختار جدید")

    result = await equipment_repository.get_action_text("xray", "structure")
    assert result == "ساختار جدید"


@pytest.mark.asyncio
async def test_update_action_text_only_touches_the_given_column(temp_equipment_db):
    """آپدیت یک ستون نباید هیچ ستون دیگری از همان ردیف را دست بزند."""
    await equipment_repository.update_action_text("xray", "structure", "ساختار جدید")

    unrelated = await equipment_repository.get_action_text("xray", "safety")
    assert unrelated == "نکات ایمنی"


@pytest.mark.asyncio
async def test_update_action_text_rejects_unlisted_column(temp_equipment_db):
    """همان کلاس آسیب‌پذیری بند ۳.۱ — اینجا هم برای UPDATE، نه فقط SELECT."""
    with pytest.raises(ValueError):
        await equipment_repository.update_action_text("xray", "secret_admin_column", "hacked")

    # جدول باید دست‌نخورده مانده باشد
    result = await equipment_repository.get_action_text("xray", "secret_admin_column")
    assert result is None  # چون get_action_text هم آن را رد می‌کند، نه چون واقعاً None است


@pytest.mark.asyncio
async def test_update_action_text_rejects_sql_injection_attempt(temp_equipment_db):
    with pytest.raises(ValueError):
        await equipment_repository.update_action_text(
            "xray", "structure; DROP TABLE information;--", "hacked",
        )

    # جدول هنوز باید سالم باشد
    result = await equipment_repository.get_action_text("xray", "structure")
    assert result == "ساختار دستگاه"
