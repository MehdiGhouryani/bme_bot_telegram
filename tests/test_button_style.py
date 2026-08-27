# tests/test_button_style.py
#
# تست styled_button: تایید می‌کنه که style واقعاً داخل to_dict() نهایی
# (همون چیزی که به‌عنوان JSON به تلگرام ارسال می‌شه) ظاهر می‌شه، و بقیه‌ی
# آرگومان‌های معمول InlineKeyboardButton (callback_data و ...) دست‌نخورده
# باقی می‌مونن.

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils import button_style  # noqa: E402


def test_styled_button_includes_style_in_serialized_output():
    btn = button_style.styled_button("🚫 مسدود کردن", button_style.DANGER, callback_data="ban:1")

    serialized = btn.to_dict()

    assert serialized["style"] == "danger"
    assert serialized["callback_data"] == "ban:1"
    assert serialized["text"] == "🚫 مسدود کردن"


def test_styled_button_success_style():
    btn = button_style.styled_button("✅ رفع مسدودی", button_style.SUCCESS, callback_data="unban:1")
    assert btn.to_dict()["style"] == "success"


def test_styled_button_primary_style():
    btn = button_style.styled_button("✏️ ویرایش", button_style.PRIMARY, callback_data="edit:1")
    assert btn.to_dict()["style"] == "primary"


def test_styled_button_still_a_real_inline_keyboard_button():
    from telegram import InlineKeyboardButton

    btn = button_style.styled_button("متن", button_style.DANGER, callback_data="x")
    assert isinstance(btn, InlineKeyboardButton)
