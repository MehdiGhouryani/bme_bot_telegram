# src/bme_bot/logging_setup.py
#
# سیستم لاگ‌نویسی متمرکز ربات. جایگزین logging.basicConfig قدیمی که فرمتش
# فاقد %(message)s بود (فقط «زمان - نام‌ماژول - سطح» چاپ می‌شد، بدون خودِ
# متن پیام) و لاگ را فقط به stdout می‌فرستاد (با هر ری‌استارت از بین می‌رفت،
# روی دیسک ذخیره نمی‌شد).
#
# --- تصمیم‌های طراحی ---
# ۱) RotatingFileHandler استاندارد پایتون (بدون وابستگی جدید) به‌جای
#    TimedRotatingFileHandler — سقف دیسک باید حجم‌محور و قطعی باشد؛ چرخش
#    زمان‌محور (روزانه) نمی‌تواند یک روز پرترافیک را از سقف دور نگه دارد.
# ۲) فرمت تک‌خطی فشرده (سطح تک‌حرفی E/W/I، بدون میلی‌ثانیه، بدون سال) تا سقف
#    صرف حجم واقعی خطا شود نه قالب‌بندی. برای خطاهای واقعی (exc_info=True،
#    مثل error_reporting.report_error)، traceback کامل و بدون فشرده‌سازی در
#    همان خط چندسطری خودش لاگ می‌شود — حذف اطلاعات از ERRORها به قیمت
#    غیرقابل‌دیباگ‌شدن‌شان تمام می‌شود، پس این فرمت فقط قالب هر خط را فشرده
#    می‌کند، نه محتوای traceback را.
# ۳) خاموش‌کردن httpx/httpcore/telegram/LiteLLM در سطح INFO: طبق مستندات
#    رسمی python-telegram-bot، از httpx>=0.24.1 هر درخواست HTTP (یعنی هر
#    polling call) در سطح INFO لاگ می‌شود. بدون این خط، بیشتر سقف دیسک صرف
#    نویز HTTP می‌شد، نه لاگ واقعی خودِ ربات.
# ۴) سقف ۱۰MB با _TruncatingRotatingFileHandler، نه RotatingFileHandler
#    استاندارد با backupCount=0. این یک گیر واقعی و مستند پایتونه: وقتی
#    backupCount==0، خودِ doRollover() هیچ rename/rotate‌ای انجام نمی‌دهد
#    (شرط `if self.backupCount > 0` کل بدنه را رد می‌کند) و فقط استریم را
#    می‌بندد و دوباره در همان حالت append باز می‌کند - یعنی فایل هرگز واقعاً
#    truncate نمی‌شود و بی‌نهایت رشد می‌کند. ساب‌کلاس زیر doRollover را
#    override می‌کند تا واقعاً فایل را خالی کند - سقف قطعی ۱۰MB، بدون تاریخچه.
# ۵) TelegramAdminErrorHandler (در utils/telegram_error_handler.py) به root
#    logger اضافه می‌شود تا هر ERROR+، از هرجای کد، مستقیم به ادمین اصلی برسد.

import logging
import os
from logging.handlers import RotatingFileHandler

from . import config
from .utils.telegram_error_handler import TelegramAdminErrorHandler

_LOG_FORMAT = "%(asctime)s|%(levelname).1s|%(name)s|%(message)s"
_DATE_FORMAT = "%m-%d %H:%M:%S"

_MAX_BYTES_PER_FILE = 10 * 1024 * 1024  # سقف قطعی ۱۰MB - بدون تاریخچه

# کتابخانه‌های ثالثی که در سطح INFO بیش‌ازحد پرحرف‌اند.
_NOISY_LOGGER_NAMES = ("httpx", "httpcore", "telegram", "LiteLLM")


class _TruncatingRotatingFileHandler(RotatingFileHandler):
    """مثل RotatingFileHandler استاندارد، ولی doRollover واقعاً فایل را
    خالی می‌کند (نه rename به .1/.2/...) — چون backupCount=0 در پیاده‌سازی
    استاندارد پایتون اصلاً rollover واقعی انجام نمی‌دهد (بالا توضیح داده شد).
    نتیجه: همیشه دقیقاً یک فایل، هرگز بیشتر از maxBytes، بدون تاریخچه."""

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        open(self.baseFilename, "w", encoding=self.encoding or "utf-8").close()
        if not self.delay:
            self.stream = self._open()


def configure_logging() -> None:
    """جایگزین logging.basicConfig قدیمی. باید یک‌بار، در ابتدای main()، پیش
    از هر فراخوانی logging.getLogger(__name__) واقعی دیگر صدا زده شود
    (خودِ getLogger مشکلی ندارد، فقط handler ها تا این تابع صدا زده نشوند
    ثبت نمی‌شوند)."""
    os.makedirs(config.LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = _TruncatingRotatingFileHandler(
        filename=os.path.join(config.LOG_DIR, "bot.log"),
        maxBytes=_MAX_BYTES_PER_FILE,
        backupCount=0,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    telegram_handler = TelegramAdminErrorHandler()
    telegram_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(telegram_handler)

    for noisy_logger_name in _NOISY_LOGGER_NAMES:
        logging.getLogger(noisy_logger_name).setLevel(logging.WARNING)

