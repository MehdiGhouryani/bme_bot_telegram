# tests/test_error_fingerprint.py

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils import error_fingerprint  # noqa: E402
from bme_bot.utils import text_chunking  # noqa: E402


def _raise_from_real_app_code():
    """یه exception واقعی با traceback واقعی که ریشه‌اش داخل کد خودِ
    پروژه (utils/text_chunking.py) است — نه یه exception دستی‌ساخته‌شده
    بدون __traceback__ (که چیزی برای fingerprint کردن نداره)."""
    try:
        text_chunking.split_into_chunks(None)
    except Exception as e:
        return e


def test_fingerprint_identifies_real_app_code_location():
    error = _raise_from_real_app_code()

    location = error_fingerprint.location_for(error)

    assert location.startswith("utils/text_chunking.py:")
    assert error_fingerprint.fingerprint_for(error) == f"TypeError@{location}"


def test_same_bug_raised_twice_produces_identical_fingerprint():
    """رجوع به utils/error_fingerprint.py: دو رخداد از دقیقاً همون باگ
    باید دقیقاً همون اثرانگشت رو بدن — این خودِ شرطِ کارکردِ dedupه."""
    first = _raise_from_real_app_code()
    second = _raise_from_real_app_code()

    assert error_fingerprint.fingerprint_for(first) == error_fingerprint.fingerprint_for(second)


def test_different_exception_types_produce_different_fingerprints():
    try:
        raise ValueError("یه چیز دیگه")
    except ValueError as e:
        other = e

    real_error = _raise_from_real_app_code()

    assert error_fingerprint.fingerprint_for(real_error) != error_fingerprint.fingerprint_for(other)


def test_error_without_traceback_falls_back_gracefully_not_crash():
    """یه exception دستی‌ساخته‌شده (نه raise شده، مثل بعضی تست‌های خودِ
    error_reporting) هیچ __traceback__ ای نداره — نباید کرش کنه، باید یه
    fallback قابل‌فهم بده."""
    error = RuntimeError("دستی‌ساخته‌شده")

    assert error_fingerprint.location_for(error) == "unknown"
    assert error_fingerprint.fingerprint_for(error) == "RuntimeError@unknown"
