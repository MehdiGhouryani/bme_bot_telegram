# tests/test_menu_builder.py
#
# این تست‌ها اطمینان می‌دهند که equipment_menu.json و menu_builder.py دقیقاً
# همان درختی را می‌سازند که کد قدیمی (keyboards_medical.py + callback_map.py)
# می‌ساخت — بدون هیچ گره‌ی آویزان (dangling reference) یا تداخل نام‌گذاری.

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import equipment_tree  # noqa: E402
from bme_bot.keyboards import menu_builder  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_tree_cache():
    # کش درخت حالا در equipment_tree.py زندگی می‌کند (menu_builder فقط رندر می‌کند)
    equipment_tree._TREE = None
    yield
    equipment_tree._TREE = None


def _load_raw_tree():
    with open(PROJECT_ROOT / "data" / "equipment_menu.json", encoding="utf-8") as f:
        return json.load(f)


def test_tree_has_expected_shape():
    tree = _load_raw_tree()
    # main_keyboard قدیمی ۷ ردیف مجزا بود، هرکدام با یک دکمه (نه یک ردیف با ۷ دکمه)
    assert len(tree["main_menu"]) == 7
    assert all(len(row) == 1 for row in tree["main_menu"])
    assert len(tree["menus"]) == 37
    assert len(tree["device_line"]) == 76
    assert len(tree["device_detail_template"]) == 4


def test_no_dangling_references():
    """هر شناسه‌ای که به‌عنوان مقصد یک دکمه ظاهر می‌شود، باید یا یک منو، یا یک
    دستگاه، یا یکی از شناسه‌های ثابت ناوبری باشد."""
    tree = _load_raw_tree()
    menus = set(tree["menus"].keys())
    devices = set(tree["device_line"].keys())
    special = {"back_to_main"}

    for menu_id, rows in tree["menus"].items():
        for row in rows:
            for btn in row:
                if "url" in btn:
                    continue
                target = btn["id"]
                assert target in menus or target in devices or target in special, (
                    f"دکمه‌ی '{btn['label']}' در منوی '{menu_id}' به شناسه‌ی ناموجود "
                    f"'{target}' اشاره می‌کند"
                )


def test_no_id_collisions_between_menus_and_devices():
    tree = _load_raw_tree()
    menus = set(tree["menus"].keys())
    devices = set(tree["device_line"].keys())
    assert menus.isdisjoint(devices)


def test_main_menu_categories_are_all_valid_menus():
    tree = _load_raw_tree()
    menus = set(tree["menus"].keys())
    main_ids = {btn["id"] for row in tree["main_menu"] for btn in row}
    assert main_ids <= menus
    assert len(main_ids) == 7


def test_get_main_menu_markup_builds_seven_buttons():
    markup = menu_builder.get_main_menu_markup()
    total_buttons = sum(len(row) for row in markup.inline_keyboard)
    assert total_buttons == 7


def test_known_device_line_mapping():
    # این مقادیر مستقیماً از Diagnostic_devices در callback_map.py قدیمی می‌آیند
    assert menu_builder.get_device_line("xray") == "imaging_devices"
    assert menu_builder.get_device_line("blood_analyzers") == "laboratory_devices"


def test_device_detail_markup_hides_full_row_on_definition():
    """طبق رفتار دقیق کد قدیمی: نمایش صفحه‌ی «معرفی» کل ردیف اول (شامل «انواع
    دستگاه») را حذف می‌کند، نه فقط دکمه‌ی «معرفی دستگاه» را."""
    normal = menu_builder.get_device_detail_markup("xray", "imaging_devices", hide_definition_row=False)
    hidden = menu_builder.get_device_detail_markup("xray", "imaging_devices", hide_definition_row=True)

    normal_labels = {btn.text for row in normal.inline_keyboard for btn in row}
    hidden_labels = {btn.text for row in hidden.inline_keyboard for btn in row}

    assert "انواع دستگاه" in normal_labels
    assert "معرفی دستگاه" in normal_labels
    assert "انواع دستگاه" not in hidden_labels
    assert "معرفی دستگاه" not in hidden_labels

    # تعداد ردیف‌ها باید دقیقاً یکی کمتر باشد (ردیف اول کامل حذف شده) + دکمه‌ی بازگشت هر دو دارند
    assert len(hidden.inline_keyboard) == len(normal.inline_keyboard) - 1


def test_device_detail_callback_data_format():
    markup = menu_builder.get_device_detail_markup("xray", "imaging_devices")
    all_callbacks = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "xray:definition:imaging_devices" in all_callbacks
    assert "xray:types:imaging_devices" in all_callbacks
    assert "imaging_devices" in all_callbacks  # دکمه‌ی بازگشت
