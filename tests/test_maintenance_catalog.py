# tests/test_maintenance_catalog.py
#
# ماژول خالص داده — تست کوچک برای اطمینان از ثبات فهرست (تعداد، یکتایی
# کلیدها، تطابق ITEM_KEYS/ITEM_LABELS با MAINTENANCE_ITEMS).

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import maintenance_catalog  # noqa: E402


def test_exactly_four_fixed_items():
    assert len(maintenance_catalog.MAINTENANCE_ITEMS) == 4


def test_item_keys_are_unique():
    keys = [key for key, _ in maintenance_catalog.MAINTENANCE_ITEMS]
    assert len(keys) == len(set(keys))


def test_item_keys_frozenset_matches_list():
    keys = {key for key, _ in maintenance_catalog.MAINTENANCE_ITEMS}
    assert maintenance_catalog.ITEM_KEYS == frozenset(keys)


def test_get_label_returns_correct_persian_label():
    assert maintenance_catalog.get_label("spare_parts") == "قطعات مهم و یدکی"


def test_get_label_falls_back_to_key_for_unknown():
    assert maintenance_catalog.get_label("not_a_real_key") == "not_a_real_key"


def test_no_separator_characters_in_item_keys():
    """item_key بخشی از callback_data می‌شود؛ اگر روزی ':' داخلش باشد،
    decode سمت هندلرها را می‌شکند."""
    for key, _ in maintenance_catalog.MAINTENANCE_ITEMS:
        assert ":" not in key
