# src/bme_bot/utils/button_style.py
#
# رنگ دکمه (فیلد style روی InlineKeyboardButton/KeyboardButton) از Bot API
# 9.4 (۹ فوریه‌ی ۲۰۲۶) اضافه شده — ولی python-telegram-bot==21.4 (نسخه‌ی
# pin‌شده‌ی requirements.txt این پروژه، از قبل از آن تاریخ) نه فیلد رسمی
# style را می‌شناسد و نه هیچ فیلد دیگری از Bot API 9.4 به بعد را.
#
# آپگرید کل python-telegram-bot صرفاً برای این یک فیلد، ریسک رگرشن روی کل
# پروژه (همه‌ی ConversationHandler ها، همه‌ی handler ها) دارد که با هدف این
# تغییر (یک بهبود UI کوچک) اصلاً تناسب ندارد. راه‌حل درست‌تر: هر دو کلاس
# InlineKeyboardButton/KeyboardButton از api_kwargs پشتیبانی می‌کنند — مکانیزم
# رسمی خودِ PTB برای دقیقاً همین حالت (فیلدهای جدیدتر از نسخه‌ی نصب‌شده) — و
# TelegramObject.to_dict() محتوای api_kwargs را مستقیم داخل دیکشنری خروجی
# نهایی merge می‌کند، یعنی وقتی درخواست HTTP واقعی به تلگرام ارسال می‌شود
# style هم داخل JSON هست، دقیقاً مثل اینکه PTB خودش این فیلد را می‌شناخت.
# (تایید شده با بررسی مستقیم رفتار نصب‌شده‌ی پروژه، نه فقط مستندات.)
#
# نکته‌ی مهم: برخلاف icon_custom_emoji_id (که نیاز به اشتراک تلگرام پرمیوم
# برای *صاحب بات* دارد)، فیلد style هیچ نیاز به پرمیومی ندارد — برای همه‌ی
# بات‌ها و همه‌ی کاربران به‌صورت پیش‌فرض کار می‌کند.

from telegram import InlineKeyboardButton

# مقادیر مجاز طبق مستندات رسمی Bot API 9.4.
DANGER = "danger"     # قرمز — اکشن‌های مخرب/غیرقابل‌بازگشت (حذف، مسدودسازی)
SUCCESS = "success"   # سبز — تایید/اکشن مثبت (رفع مسدودیت، تایید نهایی)
PRIMARY = "primary"   # آبی — اکشن اصلی/پیشنهادی صفحه


def styled_button(text: str, style: str, **kwargs) -> InlineKeyboardButton:
    """InlineKeyboardButton معمولی به‌علاوه‌ی رنگ. kwargs همون آرگومان‌های
    معمول InlineKeyboardButton هستن (callback_data، url و امثالش).

    اگه کلاینت کاربر به‌قدر کافی جدید نباشه که style رو بشناسه، تلگرام این
    فیلد رو نادیده می‌گیره و دکمه با رنگ پیش‌فرض نمایش داده می‌شه — بدون خطا،
    بدون افت رفتار (graceful degradation طبیعی خود Bot API).
    """
    return InlineKeyboardButton(text, api_kwargs={"style": style}, **kwargs)
