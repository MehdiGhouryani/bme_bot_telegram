# src/bme_bot/utils/date_time_entity.py
#
# entity نوع "date_time" در MessageEntity از قبل از Bot API 10.x وجود
# داشته و فیلد wire اصلی‌اش unix_time است — نه date_time (که فقط نام
# attribute کلاس در برخی کتابخانه‌هاست؛ تایید شده مستقیم از مستندات رسمی
# core.telegram.org/bots/api#messageentity، نه حدس زده‌شده از روی نام
# کلاس). python-telegram-bot==21.4 (نسخه‌ی pin‌شده‌ی این پروژه) این فیلد
# را نمی‌شناسد — دقیقاً همان راه‌حل api_kwargs که در utils/button_style.py
# مستندسازی شده این‌جا هم به کار می‌رود.
#
# offset/length بر پایه‌ی UTF-16 code unit است (utf16_len از
# utils/text_chunking.py — همون‌جا که سقف طول پیام هم همین نکته رو داره،
# رجوع به توضیح کامل‌تر اونجا).

from datetime import datetime

from telegram import MessageEntity

from .text_chunking import utf16_len


def date_time_entity(preceding_text: str, value_text: str, dt: datetime) -> MessageEntity:
    """MessageEntity نوع date_time برای بخشی از پیام که متنش دقیقاً برابر
    value_text است و بلافاصله بعد از preceding_text (یعنی تمام متنی که از
    ابتدای پیام تا همین‌جا رفته) شروع می‌شود.

    dt باید timezone-aware باشد — تایم‌استمپ یونیکس نهایی مستقیماً از
    dt.timestamp() محاسبه می‌شود که برای یک datetime بدون tzinfo بر پایه‌ی
    تایم‌زون محلی سیستم عمل می‌کند، نه UTC؛ در حالی‌که این پروژه همه‌جا
    (users_repository.py) تاریخ‌ها را با UTC ذخیره می‌کند.
    """
    if dt.tzinfo is None:
        raise ValueError("date_time_entity نیاز به datetime timezone-aware دارد (نه naive).")
    return MessageEntity(
        type="date_time",
        offset=utf16_len(preceding_text),
        length=utf16_len(value_text),
        api_kwargs={"unix_time": int(dt.timestamp())},
    )
