# src/bme_bot/utils/telegram_error_handler.py
#
# logging.Handler که هر رکورد سطح ERROR+ را — از هرجای کد، مستقل از این‌که
# آن نقطه صراحتاً error_reporting.report_error را صدا زده یا نه — مستقیم به
# ادمین اصلی می‌فرستد. این یک شبکه‌ی ایمنی سراسری است، مکمل
# error_reporting.py (نه جایگزینش).
#
# چرا از error_reporting.py مجزاست: آن ماژول مخصوص شکست‌های شناخته‌شده‌ی
# فیچرهاست (context_label، failure_feature، پیام کاربرپسند به کاربر) —
# این ماژول برعکس، برای چیزهایی است که هیچ نقطه‌ای صراحتاً پیش‌بینی‌شان
# نکرده (یک exception ناگهانی جایی که کسی report_error را صدا نزده).
#
# نکات فنی حیاتی:
# ۱) logging.Handler.emit() سینک است ولی ارسال تلگرام async - با
#    asyncio.get_running_loop().create_task() به لوپ در حال اجرا سپرده
#    می‌شود؛ چون کل بات async است، تقریباً همیشه یک لوپ در حال اجراست.
# ۲) رکوردهای خودِ error_reporting.py و همین ماژول عمداً نادیده گرفته
#    می‌شوند - وگرنه هر خطایی که از مسیر report_error می‌رود، به ادمین
#    دوبار می‌رسید (یک‌بار از notify_admins خودِ آن ماژول، یک‌بار از اینجا).
# ۳) هرگز از logger.* داخل خودِ این هندلر استفاده نمی‌شود - ریسک حلقه‌ی
#    بی‌نهایت اگر ارسال تلگرام خودش خطا بدهد.

from __future__ import annotations

import asyncio
import logging
import time

from .. import config

_ALERT_THROTTLE_SECONDS = 600  # هم‌راستا با error_reporting._should_send_alert
_MAX_MESSAGE_LENGTH = 3500  # حاشیه‌ی امن زیر سقف ۴۰۹۶ کاراکتر تلگرام
_EXCLUDED_LOGGER_NAMES = ("bme_bot.utils.error_reporting", __name__)

_bot = None  # با set_bot() در app.main() بلافاصله بعد از ساخت Application ست می‌شود


def set_bot(bot) -> None:
    """باید دقیقاً یک‌بار، در main()، بلافاصله بعد از Application.builder()...build() صدا زده شود."""
    global _bot
    _bot = bot


class TelegramAdminErrorHandler(logging.Handler):
    def __init__(self, level: int = logging.ERROR):
        super().__init__(level=level)
        self._last_sent_at: dict[str, float] = {}

    def _should_send(self, key: str) -> bool:
        now = time.monotonic()
        last = self._last_sent_at.get(key)
        if last is not None and (now - last) < _ALERT_THROTTLE_SECONDS:
            return False
        self._last_sent_at[key] = now
        return True

    def emit(self, record: logging.LogRecord) -> None:
        if record.name in _EXCLUDED_LOGGER_NAMES:
            return
        if _bot is None or not config.MAIN_ADMIN_CHAT_ID:
            return

        key = f"{record.name}|{record.getMessage()[:80]}"
        if not self._should_send(key):
            return

        try:
            formatted = self.format(record)
        except Exception:
            formatted = record.getMessage()

        text = f"🚨 خطای خودکار در {record.name}\n\n{formatted[:_MAX_MESSAGE_LENGTH]}"

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # لوپی در حال اجرا نیست (مثلاً هنگام تست بدون asyncio) - نادیده گرفته می‌شود
        loop.create_task(self._send(text))

    async def _send(self, text: str) -> None:
        try:
            await _bot.send_message(chat_id=config.MAIN_ADMIN_CHAT_ID, text=text)
        except Exception:
            pass  # عمداً logger.* صدا زده نمی‌شود - همان ریسک حلقه بالا
