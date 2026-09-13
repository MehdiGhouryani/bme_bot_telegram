# tests/test_education.py
#
# education.py قبلاً هیچ تست مستقلی نداشت — این فایل فقط رو تابعی که همین
# الان تغییر کرد (_build_link_keyboard) و صدازننده‌های مستقیمش تمرکز داره،
# نه یه تلاش برای پوشش کامل کل فایل (طبق قرارداد پروژه: تست فقط برای کدی
# نوشته می‌شود که مستقیم تغییر می‌کند).

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.handlers import education  # noqa: E402


def test_build_link_keyboard_normal_case_builds_all_buttons():
    url_map = {"a": "https://example.com/a", "b": "https://example.com/b"}
    layout = [[{"label": "دکمه‌ی A", "key": "a"}, {"label": "دکمه‌ی B", "key": "b"}]]

    markup = education._build_link_keyboard(url_map, layout)

    assert len(markup.inline_keyboard) == 1
    labels = [btn.text for btn in markup.inline_keyboard[0]]
    urls = [btn.url for btn in markup.inline_keyboard[0]]
    assert labels == ["دکمه‌ی A", "دکمه‌ی B"]
    assert urls == ["https://example.com/a", "https://example.com/b"]


def test_build_link_keyboard_skips_missing_key_instead_of_crashing(caplog):
    """رگرسیون: قبلاً url_map[item['key']] مستقیم بود — اگه layout به یه
    key اشاره می‌کرد که تو url_map نبود (مثلاً یه ناهماهنگی دستی موقع
    ویرایش sensors_components.json)، کل هندلر با KeyError کرش می‌کرد و
    کاربر حتی دکمه‌های سالم رو هم نمی‌دید."""
    url_map = {"a": "https://example.com/a"}
    layout = [[{"label": "دکمه‌ی A", "key": "a"}, {"label": "دکمه‌ی گمشده", "key": "missing_key"}]]

    markup = education._build_link_keyboard(url_map, layout)

    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    assert labels == ["دکمه‌ی A"]  # فقط دکمه‌ی سالم مونده
    assert "missing_key" in caplog.text  # هشدار لاگ شده، نه بی‌سروصدا


def test_build_link_keyboard_drops_row_that_becomes_entirely_empty():
    """اگه *همه‌ی* دکمه‌های یه ردیف key نامعتبر داشته باشن، اون ردیف
    باید کلاً حذف بشه (نه یه ردیف خالی تو کیبورد)."""
    url_map = {"good": "https://example.com/good"}
    layout = [
        [{"label": "سالم", "key": "good"}],
        [{"label": "خراب ۱", "key": "bad1"}, {"label": "خراب ۲", "key": "bad2"}],
    ]

    markup = education._build_link_keyboard(url_map, layout)

    assert len(markup.inline_keyboard) == 1
    assert markup.inline_keyboard[0][0].text == "سالم"


def test_build_link_keyboard_empty_layout_returns_empty_markup():
    markup = education._build_link_keyboard({}, [])
    assert list(markup.inline_keyboard) == []
