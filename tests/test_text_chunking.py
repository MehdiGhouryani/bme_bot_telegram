# tests/test_text_chunking.py
#
# text_chunking.py قبلاً هیچ تست مستقلی نداشت (فقط از طریق ocr.py/stt.py/
# ai_assistant.py غیرمستقیم استفاده می‌شد). تمرکز این فایل روی نکته‌ی
# UTF-16 است — سقف واقعی تلگرام (که split_into_chunks باید رعایتش کنه)
# بر پایه‌ی UTF-16 code unit است، نه len() ساده‌ی پایتون.

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils import text_chunking  # noqa: E402


def test_utf16_len_ascii_matches_python_len():
    assert text_chunking.utf16_len("hello") == 5


def test_utf16_len_persian_text_one_unit_per_character():
    text = "متن فارسی"
    assert text_chunking.utf16_len(text) == len(text)


def test_utf16_len_emoji_outside_bmp_counts_as_two_units():
    # 👤 (U+1F464) — تایید شده با ord() که خارج از BMP است (برخلاف مثلاً
    # ✅/⏳ که با این‌که ظاهراً هم ایموجی‌ان، کدپوینتشون داخل BMP و ۱ واحدی
    # است — نباید فرض کرد هر ایموجی‌ای لزوماً خارج از BMP است).
    assert ord("👤") > 0xFFFF
    assert len("👤") == 1  # len() پایتون: ۱ کدپوینت
    assert text_chunking.utf16_len("👤") == 2  # واقعیت UTF-16: ۲ واحد


def test_split_into_chunks_short_text_single_chunk():
    assert text_chunking.split_into_chunks("سلام") == ["سلام"]


def test_split_into_chunks_empty_text_no_chunks():
    assert text_chunking.split_into_chunks("") == []


def test_split_into_chunks_respects_max_length_for_plain_ascii():
    text = "x" * 10000
    chunks = text_chunking.split_into_chunks(text, max_length=4096)
    assert len(chunks) == 3
    assert [len(c) for c in chunks] == [4096, 4096, 10000 - 2 * 4096]
    assert "".join(chunks) == text


def test_split_into_chunks_never_exceeds_max_length_in_utf16_units_with_emoji():
    # ۵۰۰۰ تای 👤 (U+1F464، تایید‌شده خارج از BMP) پشت‌سرهم — یعنی از نظر
    # len() پایتون فقط ۵۰۰۰ کاراکتره، ولی از نظر UTF-16 واقعی ۱۰۰۰۰ واحده.
    text = "👤" * 5000

    chunks = text_chunking.split_into_chunks(text, max_length=4096)

    assert "".join(chunks) == text
    for chunk in chunks:
        assert text_chunking.utf16_len(chunk) <= 4096
    # با len() ساده (باگ قدیمی) فقط ۲ تکه می‌شد (۴۰۹۶+۹۰۴ کاراکتر) که هرکدوم
    # ۸۱۹۲/۱۸۰۸ واحد UTF-16 واقعی داشتن — یعنی هردو تکه از سقف رد می‌شدن.
    assert len(chunks) > 2


def test_split_into_chunks_mixed_text_and_emoji_stays_under_limit_and_reconstructs():
    text = ("سلام دوست من " + "👤") * 400

    chunks = text_chunking.split_into_chunks(text, max_length=100)

    assert "".join(chunks) == text
    for chunk in chunks:
        assert text_chunking.utf16_len(chunk) <= 100
