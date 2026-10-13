# src/bme_bot/utils/error_fingerprint.py
#
# اثرانگشت کوتاه و پایدار برای یک exception — پایه‌ی مکانیزم dedup در
# error_reporting.py/db/error_log_repository.py: «نوع خطا + عمیق‌ترین
# فریمِ *کد خودِ این پروژه* در traceback» (نه فریم‌های داخلی
# python-telegram-bot/httpx/aiosqlite که تقریباً همیشه بی‌ربطن و محل
# واقعی باگ رو گم می‌کنن). دو رخداد از *همون* باگ (مثلاً همون حلقه‌ی کرش
# equipment_admin_edit که با چند دکمه‌ی مختلف پشت‌سرهم تکرار شد) باید
# دقیقاً همین اثرانگشت رو بدن تا لایه‌ی dedup بتونه تشخیصش بده.

import os
import traceback

# نشونه‌ی مسیر برای جدا کردن فریم‌های «کد خودمون» از کتابخونه‌های
# نصب‌شده — کار می‌کنه چه در محیط توسعه (این ریپو) چه در دیپلوی واقعی
# (/root/bme_bot_telegram/src/bme_bot/...، رجوع به README) چون هردو زیر
# src/bme_bot/ سازمان‌دهی شدن.
_APP_PATH_MARKER = f"src{os.sep}bme_bot{os.sep}"


def _deepest_app_frame(tb) -> tuple[str, int] | None:
    """آخرین (عمیق‌ترین) فریم traceback که داخل کد خودِ پروژه‌ست، یا
    None اگه به هر دلیلی (مثلاً exception ای که کاملاً داخل یه کتابخونه
    رخ داده) هیچ فریمی از کد ما توی traceback نبود."""
    app_frame = None
    for frame_summary in traceback.extract_tb(tb):
        normalized = frame_summary.filename.replace(os.sep, "/")
        if _APP_PATH_MARKER.replace(os.sep, "/") in normalized:
            app_frame = frame_summary
    if app_frame is None:
        return None
    return app_frame.filename.replace(os.sep, "/"), app_frame.lineno


def location_for(error: BaseException) -> str:
    """رشته‌ی خوانا و کوتاهِ محل خطا، نسبی از src/bme_bot/ (مستقل از این‌که
    مسیر واقعی دیپلوی چیه) — مثلاً "handlers/ocr.py:214". اگه هیچ فریمی از
    کد ما پیدا نشد (نادر)، یه fallback قابل‌فهم (نه یه استثنای دیگه) برمی‌گردونه."""
    frame = _deepest_app_frame(error.__traceback__)
    if frame is None:
        return "unknown"
    filename, lineno = frame
    marker = _APP_PATH_MARKER.replace(os.sep, "/")
    if marker in filename:
        rel = filename.split(marker, 1)[1]
    else:
        # fallback دفاعی — عملاً نباید پیش بیاد چون _deepest_app_frame از
        # قبل با همین marker فیلتر کرده، ولی برای اطمینان نگه داشته شده.
        rel = "/".join(filename.split("/")[-2:])
    return f"{rel}:{lineno}"


def fingerprint_for(error: BaseException) -> str:
    """اثرانگشت کامل و پایدار: "نوع_خطا@محل". دو رخداد از دقیقاً همون
    باگ همیشه همین رشته رو تولید می‌کنن، بدون توجه به این‌که پیام خطا یا
    مقادیر داخلش چی بوده — عمداً؛ خودِ پیام (که می‌تونه شامل داده‌ی کاربر
    باشه) وارد این اثرانگشت نمی‌شه."""
    return f"{type(error).__name__}@{location_for(error)}"
