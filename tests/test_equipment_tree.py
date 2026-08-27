# tests/test_equipment_tree.py
#
# تست‌های ماژول equipment_tree.py — منطق خالص درخت تجهیزات (بدون telegram):
# اعتبارسنجی fail-fast، codec مشترک encode/decode_device_action، و اینکه
# get_allowed_actions() واقعاً تنها منبع حقیقت است (نه یک لیست هاردکد جدا).

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import equipment_tree  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_tree_cache():
    equipment_tree._TREE = None
    yield
    equipment_tree._TREE = None


# --- codec ---

def test_encode_decode_roundtrip():
    encoded = equipment_tree.encode_device_action("xray", "definition", "imaging_devices")
    assert encoded == "xray:definition:imaging_devices"
    assert equipment_tree.decode_device_action(encoded) == ("xray", "definition", "imaging_devices")


def test_decode_invalid_format_returns_none():
    assert equipment_tree.decode_device_action("no_colons_here") is None
    assert equipment_tree.decode_device_action("only:one_colon") is None


def test_decode_preserves_extra_colons_in_third_field():
    # maxsplit=2 یعنی فقط دو جداکننده‌ی اول معنا دارند؛ اگر line به هر دلیلی
    # کاراکتر ':' داشته باشد (که با _validate_tree نباید داشته باشد)، حداقل
    # قسمت‌های اول/دوم درست جدا می‌شوند.
    decoded = equipment_tree.decode_device_action("xray:definition:weird:line")
    assert decoded == ("xray", "definition", "weird:line")


# --- get_allowed_actions: تنها منبع حقیقت ---

def test_get_allowed_actions_matches_template_exactly():
    tree_actions = {
        item["action"]
        for row in equipment_tree.get_device_detail_template()
        for item in row
    }
    assert equipment_tree.get_allowed_actions() == frozenset(tree_actions)
    assert len(equipment_tree.get_allowed_actions()) == 7


# --- is_menu / is_device / get_device_line ---

def test_is_menu_and_is_device_are_mutually_exclusive():
    assert equipment_tree.is_menu("imaging_devices") is True
    assert equipment_tree.is_device("imaging_devices") is False

    assert equipment_tree.is_device("xray") is True
    assert equipment_tree.is_menu("xray") is False


def test_unknown_id_is_neither_menu_nor_device():
    assert equipment_tree.is_menu("totally_made_up_id") is False
    assert equipment_tree.is_device("totally_made_up_id") is False


def test_get_device_line_known_device():
    assert equipment_tree.get_device_line("xray") == "imaging_devices"


# --- _validate_tree: fail-fast ---

def test_validate_tree_rejects_colon_in_menu_id():
    bad_tree = {
        "main_menu": [],
        "menus": {"bad:menu": []},
        "device_line": {},
        "device_detail_template": [],
    }
    with pytest.raises(ValueError, match="equipment_menu.json نامعتبر است"):
        equipment_tree._validate_tree(bad_tree)


def test_validate_tree_rejects_colon_in_device_id():
    bad_tree = {
        "main_menu": [],
        "menus": {},
        "device_line": {"bad:device": "some_menu"},
        "device_detail_template": [],
    }
    with pytest.raises(ValueError):
        equipment_tree._validate_tree(bad_tree)


def test_validate_tree_rejects_colon_in_action_name():
    bad_tree = {
        "main_menu": [],
        "menus": {},
        "device_line": {},
        "device_detail_template": [[{"label": "x", "action": "bad:action"}]],
    }
    with pytest.raises(ValueError):
        equipment_tree._validate_tree(bad_tree)


def test_validate_tree_accepts_the_real_data_file():
    # اگر data/equipment_menu.json واقعی خودش نامعتبر بود، این تست شکست می‌خورد
    equipment_tree._load_tree()  # نباید هیچ استثنایی بیندازد
