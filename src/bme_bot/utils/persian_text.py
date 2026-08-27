# src/bme_bot/utils/persian_text.py
#
# نرمال‌سازی سبک متن فارسی برای خروجی OCR.
#
# *** چرا بدون Hazm/Parsivar ***
# این دو کتابخانه‌ی معروف NLP فارسی عمدتاً برای وظایف سنگین‌تر (توکنایز
# جمله، lemmatizer، POS tagger) ساخته شده‌اند، در حالی که نیاز واقعی همین‌جا
# فقط یکسان‌سازی حروف عربی/فارسی + اصلاح نیم‌فاصله + نرمال‌سازی اعداد است —
# کاری که با چند جایگزینی رشته‌ی ساده و بدون وابستگی جدید قابل انجام است.
# اگر در آینده نیاز به توکنایز/تصحیح املایی واقعی پیدا شد، افزودن
# Hazm/Parsivar به‌عنوان یک لایه‌ی جدا و اختیاری پیشنهاد می‌شود.

import re

# یکسان‌سازی حروف عربی رایج با معادل فارسی‌شان.
_CHAR_MAP = {
    "ي": "ی",  # ye عربی -> ye فارسی
    "ك": "ک",  # kaf عربی -> kaf فارسی
    "ة": "ه",  # ta marbuta -> he
    "ۀ": "ه",
    "ؤ": "و",
    "إ": "ا",
    "أ": "ا",
    "ٱ": "ا",
    "\u200f": "",  # RLM
    "\u200e": "",  # LRM
}

# اعداد عربی/انگلیسی -> فارسی (فقط برای نمایش؛ در صورت نیاز به رشته‌ی اصلی
# می‌توان این تبدیل را غیرفعال کرد).
_DIGIT_MAP = {
    "0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴",
    "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹",
    "٠": "۰", "١": "۱", "٢": "۲", "٣": "۳", "٤": "۴",
    "٥": "۵", "٦": "۶", "٧": "۷", "٨": "۸", "٩": "۹",
}

# ثابت _ZWNJ عمداً اینجا نیست: نیم‌فاصله (ZWNJ) بخشی از املای درست فارسی است
# (مثلاً در «می‌کنم»)، پس حذف کورکورانه‌ی همه‌ی نیم‌فاصله‌ها از متن OCR که
# برای *نمایش* به کاربر تمیز می‌شود، خودش یک باگ است، نه رفع باگ.
_TATWEEL = "\u0640"

# فاصله‌های اضافه: بیش از یک space/newline پشت‌سرهم -> یکی
_EXTRA_WHITESPACE_RE = re.compile(r"[ \t]{2,}")
_EXTRA_NEWLINES_RE = re.compile(r"\n{3,}")


def normalize(text: str, *, convert_digits: bool = True) -> str:
    """متن خام OCR را برای نمایش به کاربر فارسی‌زبان تمیز می‌کند.

    مراحل:
    ۱) یکسان‌سازی حروف عربی/فارسی
    ۲) حذف تطویل (ـ) که در OCR متون اسکن‌شده گاهی به‌اشتباه تشخیص داده می‌شود
    ۳) یکسان‌سازی اعداد (اختیاری، پیش‌فرض روشن)
    ۴) پاک‌سازی فاصله‌های اضافه/خطوط خالی اضافه
    """
    if not text:
        return text

    result = text
    for src, dst in _CHAR_MAP.items():
        result = result.replace(src, dst)

    result = result.replace(_TATWEEL, "")

    if convert_digits:
        for src, dst in _DIGIT_MAP.items():
            result = result.replace(src, dst)

    result = _EXTRA_WHITESPACE_RE.sub(" ", result)
    result = _EXTRA_NEWLINES_RE.sub("\n\n", result)
    result = "\n".join(line.strip() for line in result.split("\n"))

    return result.strip()


def looks_like_persian(text: str, *, threshold: float = 0.15) -> bool:
    """تشخیص سبک: آیا متن حاوی نسبت قابل‌توجهی از حروف فارسی/عربی است؟

    برای این‌که اگر یک لایه‌ی OCR (مثلاً OCR.space Engine 1) برای فارسی
    خروجی نامفهوم/لاتین بدهد، بتوان لایه‌ی بعدی زنجیره را امتحان کرد، بدون
    این‌که به یک کتابخانه‌ی تشخیص زبان سنگین نیاز باشد.
    """
    if not text:
        return False
    persian_chars = sum(1 for ch in text if "\u0600" <= ch <= "\u06ff")
    letters = sum(1 for ch in text if ch.isalpha() or ("\u0600" <= ch <= "\u06ff"))
    if letters == 0:
        return False
    return (persian_chars / letters) >= threshold
