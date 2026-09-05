# src/bme_bot/keyboards/reply_keyboards.py
#
# کیبورد Reply اصلی (۴ دکمه‌ی منوی اصلی). این کیبورد در دو جای مختلف ساخته
# می‌شود: یک‌بار در start() (با one_time_keyboard=True) و یک‌بار در
# handle_back_to_main() (بدون one_time_keyboard، یعنی False) — این تفاوت
# رفتاری عمدی است، نه یک ناهماهنگی که باید یکسان شود.
#
# --- چرا متن دکمه‌ها ثابت پایتون‌اند، نه رشته‌ی تایپی مستقل در app.py ---
# اگر متن هر دکمه هم اینجا (برای ساخت KeyboardButton) و هم جداگانه در app.py
# (به‌عنوان کلید دیکشنری _BUTTON_HANDLERS) با تایپ مستقل نوشته شود،
# خطرناک‌ترین سناریو دو دکمه‌ی «بازگشت» با متنی است که فقط در یک فاصله فرق
# دارد و هرکدام به مقصد متفاوتی می‌روند — اگر کسی این فاصله‌ی نامرئی را در
# یکی از دو نسخه‌ی مستقل «تمیز» کند، آن دکمه بی‌صدا از کار می‌افتد (نه خطا،
# فقط _BUTTON_HANDLERS.get(text) مقدار None برمی‌گرداند). با تعریف این
# متن‌ها این‌جا به‌عنوان ثابت پایتون و import همان ثابت‌ها در app.py (به‌جای
# تایپ مجدد رشته)، این خطر از بین می‌رود.

from telegram import KeyboardButton, ReplyKeyboardMarkup

# --- منوی اصلی ---
EDUCATION_TEXT = "📚 آموزش"
FAQ_TEXT = "❓ سوالات متداول"
SUGGESTION_TEXT = "📝 درخواست و پیشنهاد"
AI_ASK_TEXT = "💬 پرسش از هوش مصنوعی"
TOOLS_TEXT = "🛠 ابزارها"

# --- منوی آموزش ---
MEDICAL_EQUIPMENT_TEXT = "تجهیزات پزشکی  🩺"
SENSORS_COMPONENTS_TEXT = "⚙️ سنسور ها و قطعات"

# --- منوی سنسورها/قطعات ---
SENSORS_TEXT = "📡 سنسورها"
COMPONENTS_TEXT = "🔧 قطعات الکترونیکی"

# --- منوی ابزارها ---
# یک زیرمنوی جدا برای ابزارهای کمکی، تا منوی اصلی شلوغ نشود و اضافه‌کردن
# ابزار بعدی فقط نیازمند افزودن یک دکمه‌ی دیگر همین‌جا باشد.
OCR_TOOL_TEXT = "📸 تبدیل عکس به متن"
STT_TOOL_TEXT = "🎙 تبدیل ویس به متن"
QUIZ_TOOL_TEXT = "🧠 کوییز از متن"
JOZVE_TOOL_TEXT = "🎓 ویس استاد به جزوه"

# نکته‌ی مهم: این دو متن فقط در یک فاصله (بلافاصله بعد از «قبل») با هم فرق
# دارند — این تفاوت عمدی و از کد قدیمی به ارث رسیده؛ هرکدام به مقصد متفاوتی
# می‌رود (به کامنت بالای فایل مراجعه کنید).
BACK_TO_MAIN_TEXT = "بازگشت به صفحه قبل  ⬅️"       # دو فاصله → منوی اصلی
BACK_TO_EDUCATION_TEXT = "بازگشت به صفحه قبل ⬅️"    # یک فاصله → منوی آموزش

MAIN_MENU_BUTTONS = [
    [KeyboardButton(EDUCATION_TEXT), KeyboardButton(FAQ_TEXT)],
    [KeyboardButton(AI_ASK_TEXT), KeyboardButton(TOOLS_TEXT)],
    [KeyboardButton(SUGGESTION_TEXT)],
]

EDUCATION_MENU_BUTTONS = [
    [KeyboardButton(MEDICAL_EQUIPMENT_TEXT), KeyboardButton(SENSORS_COMPONENTS_TEXT)],
    [KeyboardButton(BACK_TO_MAIN_TEXT)],
]

SENSORS_COMPONENTS_MENU_BUTTONS = [
    [KeyboardButton(SENSORS_TEXT), KeyboardButton(COMPONENTS_TEXT)],
    [KeyboardButton(BACK_TO_EDUCATION_TEXT)],
]

# منوی ابزارها مستقیم زیرمجموعه‌ی منوی اصلی است (نه آموزش)، پس دکمه‌ی
# بازگشتش هم از همان BACK_TO_MAIN_TEXT استفاده می‌کند — بدون نیاز به یک
# رشته‌ی «بازگشت» سوم که فقط با یک فاصله از دوتای قبلی فرق داشته باشد.
TOOLS_MENU_BUTTONS = [
    [KeyboardButton(OCR_TOOL_TEXT)],
    [KeyboardButton(STT_TOOL_TEXT)],
    [KeyboardButton(QUIZ_TOOL_TEXT)],
    [KeyboardButton(JOZVE_TOOL_TEXT)],
    [KeyboardButton(BACK_TO_MAIN_TEXT)],
]

# همه‌ی متن‌های دکمه‌ی reply keyboard، یک‌جا — برای هندلرهایی که باید تشخیص
# بدن یه پیام متنی واقعاً محتوای تازه‌ست یا صرفاً یه تپ روی دکمه‌ی ناوبری
# (مثلاً equipment_admin_edit.py: یه ادمین که وسط ویرایش متن یه دکمه‌ی
# منو رو می‌زنه نباید نتیجه‌ش این باشه که اون متنِ دکمه به‌عنوان محتوای
# جدید ذخیره بشه). یک لاگ production واقعی این سناریو رو تایید کرد —
# تپ رو دکمه‌های ناوبری وسط ویرایش، هرکدوم جدا باعث تلاش برای ذخیره‌ی
# متن دکمه به‌جای محتوای واقعی می‌شد.
ALL_MENU_BUTTON_TEXTS = frozenset({
    EDUCATION_TEXT, FAQ_TEXT, SUGGESTION_TEXT, AI_ASK_TEXT, TOOLS_TEXT,
    MEDICAL_EQUIPMENT_TEXT, SENSORS_COMPONENTS_TEXT,
    SENSORS_TEXT, COMPONENTS_TEXT,
    OCR_TOOL_TEXT, STT_TOOL_TEXT, QUIZ_TOOL_TEXT, JOZVE_TOOL_TEXT,
    BACK_TO_MAIN_TEXT, BACK_TO_EDUCATION_TEXT,
})


# این ۴ تابع پایینی هرکدام فقط نازک‌ترین wrapper ممکن حول یک سازنده‌ی
# مشترک (_reply_keyboard) هستند — بدون آن، هر منوی Reply ساده (main/tools/
# sensors/components) باید مستقل ReplyKeyboardMarkup(..., resize_keyboard=True)
# را می‌ساخت (فقط buttons فرق می‌کرد)، و هر منوی Reply جدید یعنی یک تابع
# تکراری دیگر.
def _reply_keyboard(buttons, *, one_time: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=one_time)


def main_menu_keyboard(one_time: bool = False) -> ReplyKeyboardMarkup:
    return _reply_keyboard(MAIN_MENU_BUTTONS, one_time=one_time)


def education_menu_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard(EDUCATION_MENU_BUTTONS)


def sensors_components_menu_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard(SENSORS_COMPONENTS_MENU_BUTTONS)


def tools_menu_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard(TOOLS_MENU_BUTTONS)
