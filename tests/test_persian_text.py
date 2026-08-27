# tests/test_persian_text.py

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils import persian_text  # noqa: E402


def test_normalize_unifies_arabic_letters_to_persian():
    result = persian_text.normalize("كتاب علمي")
    assert result == "کتاب علمی"


def test_normalize_removes_tatweel():
    result = persian_text.normalize("سلامـــــ")
    assert "ـ" not in result


def test_normalize_converts_digits_to_persian_by_default():
    result = persian_text.normalize("صفحه 12 از 34")
    assert result == "صفحه ۱۲ از ۳۴"


def test_normalize_can_keep_digits_unconverted():
    result = persian_text.normalize("صفحه 12", convert_digits=False)
    assert "12" in result
    assert "۱۲" not in result


def test_normalize_collapses_extra_whitespace_and_blank_lines():
    result = persian_text.normalize("سلام    دنیا\n\n\n\nخط بعدی")
    assert "سلام دنیا" in result
    assert "\n\n\n" not in result


def test_normalize_empty_string_returns_empty_string():
    assert persian_text.normalize("") == ""


def test_looks_like_persian_true_for_persian_text():
    assert persian_text.looks_like_persian("این یک متن فارسی است") is True


def test_looks_like_persian_false_for_english_text():
    assert persian_text.looks_like_persian("This is English text") is False


def test_looks_like_persian_false_for_empty_string():
    assert persian_text.looks_like_persian("") is False
