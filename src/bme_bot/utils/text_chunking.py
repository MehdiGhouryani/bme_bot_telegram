# src/bme_bot/utils/text_chunking.py
#
# این تابع قبلاً عیناً در دو فایل تکرار شده بود — services/ai_service.py
# (به‌عنوان split_into_chunks عمومی) و handlers/ocr.py (به‌عنوان
# _split_into_chunks خصوصی، عمداً جداگانه نگه داشته شده بود تا ocr.py به
# ماژول ai_service که موضوعش کاملاً متفاوت است وابسته نباشد). آن نگرانی
# (وابستگی نامربوط بین ai_service و ocr) با انتقال منطق به این ماژول سوم
# مشترک برطرف می‌شود — نه ai_service نه ocr به هم وابسته می‌شوند، هر دو فقط
# از این utility می‌خوانند.
#
# نکته‌ی حیاتی UTF-16: سقف طول پیام/کپشن تلگرام بر پایه‌ی UTF-16 code unit
# است، نه تعداد کاراکتر پایتون (len()). کاراکترهای خارج از BMP — مثلاً
# ایموجی‌های رایج 👤/🚫/🗑/📝 (نه همه‌ی ایموجی‌ها؛ برخی مثل ✅/⏳ در واقع
# داخل BMP هستند و فقط ۱ واحدند — باید هر مورد را با ord(ch) > 0xFFFF چک
# کرد، نه فرض کرد) — هرکدام ۲ واحد UTF-16 مصرف می‌کنند ولی len() پایتون
# آن‌ها را ۱ می‌شمرد. بدون این تبدیل، تکه‌کردن متنی که حاوی این‌جور
# ایموجی‌هاست ممکنه یه تکه‌ی «۴۰۹۶ کاراکتری از نظر پایتون» تولید کنه که
# واقعاً بیشتر از سقف واقعی ۴۰۹۶-UTF-16-یونیتی تلگرامه.

MAX_TELEGRAM_MESSAGE_LENGTH = 4096


def utf16_len(text: str) -> int:
    """طول text به واحد UTF-16 code unit — همان واحدی که تلگرام برای سقف
    طول پیام/کپشن و برای offset/length در MessageEntity استفاده می‌کند."""
    return len(text.encode("utf-16-le")) // 2


def split_into_chunks(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH):
    """متن را طوری تکه‌تکه می‌کند که طول هر تکه (بر پایه‌ی UTF-16 code unit)
    از max_length بیشتر نشود. برای متن بدون کاراکتر خارج از BMP (بدون
    ایموجی)، دقیقاً هم‌ارز با تکه‌کردن ساده‌ی len()-محور قبلی است؛ فرق فقط
    وقتی بروز می‌کند که متن ایموجی خارج از BMP داشته باشد."""
    chunks = []
    current_chars: list[str] = []
    current_units = 0
    for ch in text:
        ch_units = utf16_len(ch)
        if current_units + ch_units > max_length and current_chars:
            chunks.append("".join(current_chars))
            current_chars, current_units = [], 0
        current_chars.append(ch)
        current_units += ch_units
    if current_chars:
        chunks.append("".join(current_chars))
    return chunks
