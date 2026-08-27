# tests/test_date_time_entity.py
#
# تست utf16_len (به‌خصوص روی ایموجی‌های خارج از BMP که ۲ واحد UTF-16
# مصرف می‌کنند ولی len() پایتون آن‌ها را ۱ می‌شمرد) و date_time_entity.

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils import date_time_entity  # noqa: E402


def test_utf16_len_ascii():
    assert date_time_entity.utf16_len("hello") == 5


def test_utf16_len_persian_text_stays_one_unit_per_character():
    # حروف فارسی داخل BMP هستن، پس ۱ واحد UTF-16 به ازای هر کاراکتر —
    # دقیقاً مثل len() معمولی پایتون.
    text = "نام‌کاربری"
    assert date_time_entity.utf16_len(text) == len(text)


def test_utf16_len_emoji_outside_bmp_counts_as_two_units():
    # 👤 (U+1F464) خارج از BMP است — ۲ واحد UTF-16، نه ۱ — دقیقاً همون
    # چیزی که len() پایتون اشتباه می‌گیره (۱ کدپوینت می‌شمره).
    assert len("👤") == 1  # len() پایتون: ۱ کدپوینت
    assert date_time_entity.utf16_len("👤") == 2  # واقعیت UTF-16: ۲ واحد


def test_utf16_len_mixed_emoji_and_text_matches_manual_count():
    text = "👤 کاربر 123"
    # 👤 (۲ واحد) + " کاربر 123" (۱۰ کاراکتر، همه داخل BMP)
    assert date_time_entity.utf16_len(text) == 2 + len(" کاربر 123")


def test_date_time_entity_offset_accounts_for_emoji_before_it():
    preceding = "👤 تاریخ عضویت: "
    value = "2026-08-25 10:00:00"
    dt = datetime(2026, 8, 25, 10, 0, 0, tzinfo=timezone.utc)

    entity = date_time_entity.date_time_entity(preceding, value, dt)

    assert entity.type == "date_time"
    assert entity.offset == date_time_entity.utf16_len(preceding)
    assert entity.offset == 2 + len(" تاریخ عضویت: ")  # نه len(preceding) خام
    assert entity.length == len(value)  # value کاملاً ASCII، پس مساوی len() هم هست


def test_date_time_entity_unix_time_matches_utc_timestamp():
    dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    entity = date_time_entity.date_time_entity("", "x", dt)
    assert entity.to_dict()["unix_time"] == int(dt.timestamp())


def test_date_time_entity_rejects_naive_datetime():
    naive_dt = datetime(2026, 1, 1, 0, 0, 0)  # بدون tzinfo
    with pytest.raises(ValueError):
        date_time_entity.date_time_entity("", "x", naive_dt)
