# src/bme_bot/equipment_tree.py
#
# داده و منطق خالص درخت تجهیزات (بدون هیچ وابستگی به telegram)، خوانده‌شده از
# data/equipment_menu.json.
#
# چرا این ماژول جدا از keyboards/menu_builder.py است؟
# db/equipment_repository.py (لایه‌ی دیتابیس) برای اعتبارسنجی «اکشن‌های
# مجاز» باید بداند device_detail_template چیست — اگر این منطق داخل
# keyboards/menu_builder.py می‌ماند، لایه‌ی db مجبور می‌شد از لایه‌ی نمایش
# (keyboards) importکند که جهت وابستگی اشتباهی است (داده نباید به UI وابسته
# باشد). این ماژول آن منطق خالص (بدون telegram) را جدا نگه می‌دارد تا هم
# db/equipment_repository.py و هم keyboards/menu_builder.py بدون مشکل
# لایه‌بندی از آن استفاده کنند.
#
# --- نکات امنیتی/صحت ---
# - get_allowed_actions(): تنها منبع حقیقت برای اکشن‌های مجاز؛ دیگر به‌صورت
#   جداگانه در equipment_repository.py هاردکد نیست (قبلاً می‌توانست out-of-sync
#   شود اگر کسی فقط JSON را ویرایش می‌کرد).
# - encode_device_action()/decode_device_action(): قالب callback_data سطح ۳
#   ("device:action:line") فقط در یک نقطه تعریف شده؛ ساخت و parse هر دو از
#   همین دو تابع عبور می‌کنند.
# - _validate_tree(): هنگام بارگذاری، مطمئن می‌شویم هیچ شناسه‌ای شامل جداکننده
#   نیست — وگرنه encode/decode بی‌صدا نتیجه‌ی غلط می‌دهند. اگر نقض شود، بلافاصله
#   یک ValueError واضح می‌دهد (fail-fast) به‌جای شکست خاموش در زمان اجرا.

import json

from . import config

_TREE = None

# جداکننده‌ی فرمت callback_data سطح ۳: "device{SEP}action{SEP}line"
DEVICE_ACTION_SEPARATOR = ":"


def _validate_tree(tree: dict) -> None:
    all_ids = set(tree.get("menus", {}).keys()) | set(tree.get("device_line", {}).keys())
    bad_ids = sorted(i for i in all_ids if DEVICE_ACTION_SEPARATOR in i)
    if bad_ids:
        raise ValueError(
            f"equipment_menu.json نامعتبر است: شناسه(های) {bad_ids} شامل کاراکتر "
            f"'{DEVICE_ACTION_SEPARATOR}' هستند که با فرمت callback_data "
            f"(device{DEVICE_ACTION_SEPARATOR}action{DEVICE_ACTION_SEPARATOR}line) تداخل دارد."
        )

    # اکشن‌های داخل قالب هم نباید جداکننده داشته باشند (همان دلیل بالا)
    all_actions = {item["action"] for row in tree.get("device_detail_template", []) for item in row}
    bad_actions = sorted(a for a in all_actions if DEVICE_ACTION_SEPARATOR in a)
    if bad_actions:
        raise ValueError(
            f"equipment_menu.json نامعتبر است: اکشن(های) {bad_actions} در device_detail_template "
            f"شامل کاراکتر '{DEVICE_ACTION_SEPARATOR}' هستند."
        )


def _load_tree() -> dict:
    global _TREE
    if _TREE is None:
        path = f"{config.DATA_DIR}/equipment_menu.json"
        with open(path, encoding="utf-8") as f:
            tree = json.load(f)
        _validate_tree(tree)
        _TREE = tree
    return _TREE


def get_main_menu_rows() -> list:
    """چیدمان خام (لیست ردیف‌های {label, id}) کیبورد سطح ۰."""
    return _load_tree()["main_menu"]


def is_menu(node_id: str) -> bool:
    """آیا این شناسه یک «منو»ست (سطح ۰/۱ درخت — معادل کلیدهای keyboard_map قدیمی)."""
    return node_id in _load_tree()["menus"]


def get_menu_rows(node_id: str) -> list:
    """چیدمان خام یک منوی مشخص (سطح ۱ یا ۲ درخت)."""
    return _load_tree()["menus"][node_id]


def is_device(node_id: str) -> bool:
    """آیا این شناسه یک «دستگاه» برگ درخت است (معادل کلیدهای combined_callback_map قدیمی)."""
    return node_id in _load_tree()["device_line"]


def get_device_line(node_id: str) -> str:
    """دسته‌بندی (line) مربوط به یک دستگاه را برمی‌گرداند."""
    return _load_tree()["device_line"][node_id]


def get_device_detail_template() -> list:
    """قالب خام ۷-اکشنی جزئیات دستگاه (لیست ردیف‌های {label, action})."""
    return _load_tree()["device_detail_template"]


def get_allowed_actions() -> frozenset:
    """اکشن‌های مجاز جزئیات دستگاه — تنها منبع حقیقت (به‌جای یک لیست هاردکد جدا
    در equipment_repository.py که می‌توانست از این‌جا out-of-sync شود)."""
    tree = _load_tree()
    return frozenset(item["action"] for row in tree["device_detail_template"] for item in row)


def encode_device_action(device: str, action: str, line: str) -> str:
    """قالب callback_data سطح ۳ را در یک نقطه‌ی واحد می‌سازد — طرف مقابل
    decode_device_action است."""
    return f"{device}{DEVICE_ACTION_SEPARATOR}{action}{DEVICE_ACTION_SEPARATOR}{line}"


def decode_device_action(data: str):
    """معکوس encode_device_action. در صورت فرمت نامعتبر None برمی‌گرداند،
    وگرنه tuple (device, action, line)."""
    parts = data.split(DEVICE_ACTION_SEPARATOR, 2)
    if len(parts) != 3:
        return None
    return tuple(parts)
