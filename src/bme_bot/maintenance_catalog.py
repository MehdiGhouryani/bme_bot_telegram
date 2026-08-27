# src/bme_bot/maintenance_catalog.py
#
# فهرست ثابت سراسری زیربخش‌های «تعمیرات و نگهداری» (M1/M2، طبق تصمیم شما در
# فهرست ثابت، نه دلخواه per-device).
#
# چرا یک ماژول خالص جدا (بدون telegram)، هم‌الگو با equipment_tree.py؟
# db/maintenance_repository.py برای اعتبارسنجی item_key و
# handlers/maintenance_admin_edit.py و handlers/maintenance_callbacks.py هر دو
# برای برچسب فارسی به همین فهرست نیاز دارند — یک نقطه‌ی واحد حقیقت، تا لایه‌ی
# دیتابیس مجبور به import از لایه‌ی UI نشود (همان دلیل جدایی equipment_tree.py
# از keyboards/menu_builder.py).
#
# ترتیب این لیست همان ترتیب نمایشی (هم به ادمین، هم به کاربر عادی) است.

MAINTENANCE_ITEMS = [
    ("common_failures", "خرابی‌های رایج"),
    ("troubleshooting", "راهنمای عیب‌یابی و مشاوره"),
    ("spare_parts", "قطعات مهم و یدکی"),
    ("calibration", "دوره‌ی سرویس و کالیبراسیون"),
]

# تنها منبع حقیقت برای اعتبارسنجی item_key — همان الگوی
# equipment_tree.get_allowed_actions().
ITEM_KEYS = frozenset(key for key, _ in MAINTENANCE_ITEMS)

ITEM_LABELS = dict(MAINTENANCE_ITEMS)


def get_label(item_key: str) -> str:
    """برچسب فارسی یک item_key. برای item_key نامعتبر، خودِ کلید را برمی‌گرداند
    (نباید عملاً پیش بیاید چون فراخواننده‌ها قبلش ITEM_KEYS را چک می‌کنند؛ این
    فقط یک محافظ دفاعی ارزان است، نه رفتار اصلی)."""
    return ITEM_LABELS.get(item_key, item_key)
