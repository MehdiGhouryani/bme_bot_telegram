# src/bme_bot/keyboards/menu_builder.py
#
# جایگزین کامل keyboards_medical.py (کلاس KeyboardsManager با ۳۸ متد هاردکد) و
# بخش «داده» callback_map.py (۷ دیکشنری دسته‌بندی). این فایل فقط مسئول تبدیل
# داده‌ی خام درخت (از equipment_tree.py) به آبجکت‌های واقعی تلگرام
# (InlineKeyboardMarkup/Button) است — خودِ داده و منطق خالص (بارگذاری JSON،
# اعتبارسنجی، codec) در equipment_tree.py نگه‌داری می‌شود تا لایه‌ی دیتابیس
# (equipment_repository.py) مجبور نباشد از این فایل (لایه‌ی UI) import کند.
#
# اضافه‌کردن یک دسته‌بندی/دستگاه جدید از این پس فقط به معنی افزودن یک گره به
# data/equipment_menu.json است — نیازی به لمس این فایل یا هر فایل پایتون
# دیگری نیست.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .. import equipment_tree
from . import reply_keyboards

# دکمه‌ی «بازگشت» این‌لاین درخت تجهیزات از همان مقدار متنیِ
# reply_keyboards.BACK_TO_EDUCATION_TEXT استفاده می‌کند — نه چون این دکمه به
# «آموزش» مربوط است (اصلاً نیست؛ این یک دکمه‌ی این‌لاین بر پایه‌ی callback_data
# است، نه یک دکمه‌ی Reply با تطبیق متنی مثل آن ثابت در reply_keyboards.py)،
# بلکه صرفاً برای یکسان‌بودن ظاهری متن «بازگشت» در کل ربات و جلوگیری از
# واگرایی دو رشته‌ی مستقل.
#
# عمداً یک alias محلی با نام خنثی تعریف شده به‌جای این‌که همه‌جا مستقیم از
# reply_keyboards.BACK_TO_EDUCATION_TEXT استفاده شود: آن ثابت در محل تعریفش
# نقش حیاتی در مسیریابی دکمه‌ی Reply منوی آموزش دارد (کلید دیکشنری
# app._BUTTON_HANDLERS) و همراه با BACK_TO_MAIN_TEXT یک تفاوت یک‌فاصله‌ای
# حساس و صراحتاً مستندشده است (به کامنت‌های reply_keyboards.py مراجعه کنید).
# رفرنس مستقیم آن نام از این فایل (که موضوعش کاملاً بی‌ربط به منوی آموزش
# است) می‌توانست خواننده‌ی آینده را گیج کند که این دکمه هم به منوی آموزش
# مربوط است. آدرس/مقدار یکی است، فقط نام محلی صادقانه‌تر است.
_EQUIPMENT_BACK_BUTTON_TEXT = reply_keyboards.BACK_TO_EDUCATION_TEXT

# re-export برای راحتی فراخوانی از handlers (تا آن‌ها هم منطق خالص هم رندر را
# از یک import واحد بگیرند، بدون نیاز به import مستقیم equipment_tree)
is_menu = equipment_tree.is_menu
is_device = equipment_tree.is_device
get_device_line = equipment_tree.get_device_line
encode_device_action = equipment_tree.encode_device_action
decode_device_action = equipment_tree.decode_device_action


def _rows_from_spec(rows_spec):
    rows = []
    for row_spec in rows_spec:
        row = []
        for btn in row_spec:
            if "url" in btn:
                row.append(InlineKeyboardButton(btn["label"], url=btn["url"]))
            else:
                row.append(InlineKeyboardButton(btn["label"], callback_data=btn["id"]))
        rows.append(row)
    return rows


def get_main_menu_markup() -> InlineKeyboardMarkup:
    """کیبورد سطح ۰: ۷ دسته‌بندی اصلی تجهیزات (معادل main_keyboard قدیمی)."""
    return InlineKeyboardMarkup(_rows_from_spec(equipment_tree.get_main_menu_rows()))


def get_menu_markup(node_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(_rows_from_spec(equipment_tree.get_menu_rows(node_id)))


def get_device_detail_markup(device: str, line: str, hide_definition_row: bool = False) -> InlineKeyboardMarkup:
    """منوی ثابت ۷-اکشنی جزئیات یک دستگاه را می‌سازد.

    این دقیقاً همان قالبی است که قبلاً هم در callback_map.py (تابع generate_keys)
    و هم در main.py (fetch_and_display_info) به‌طور تکراری نوشته شده بود.

    نکته‌ی مهم برای حفظ رفتار دقیق کد قدیمی: وقتی کاربر روی «معرفی دستگاه» کلیک
    می‌کند، کد قدیمی کل ردیف اول (که شامل «انواع دستگاه» هم می‌شود) را حذف
    می‌کرد، نه فقط دکمه‌ی «معرفی دستگاه» را. این رفتار (هرچند شاید عمدی نبوده)
    طبق الزام بخش ۱۲ عیناً حفظ شده است.
    """
    rows = []
    for row_spec in equipment_tree.get_device_detail_template():
        if hide_definition_row and any(item["action"] == "definition" for item in row_spec):
            continue
        row = [
            InlineKeyboardButton(
                item["label"], callback_data=equipment_tree.encode_device_action(device, item["action"], line)
            )
            for item in row_spec
        ]
        rows.append(row)
    # جزئیات alias این متن در بالای فایل.
    rows.append([InlineKeyboardButton(_EQUIPMENT_BACK_BUTTON_TEXT, callback_data=line)])
    return InlineKeyboardMarkup(rows)
