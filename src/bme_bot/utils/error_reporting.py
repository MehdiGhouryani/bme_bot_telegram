# src/bme_bot/utils/error_reporting.py
# لاگ + گزارش خطا به ادمین (با throttle). هرگز به کاربر عادی پیام نمی‌فرستد.

from __future__ import annotations

import logging
import time
import traceback

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .admin import notify_admins
from . import error_fingerprint
from ..db import error_log_repository, feature_usage_repository

logger = logging.getLogger(__name__)

_ALERT_THROTTLE_SECONDS = 600
_last_alert_at: dict[str, float] = {}

# برای escape کردن کاراکترهای خاص Markdown (legacy، نه MarkdownV2) قبل از
# قرار گرفتن تو یه پیام که parse_mode=MARKDOWN داره — چون context_label و
# str(error) متن خامِ کاربر/exception ان (مثلاً یه پیام کاربر که خودش یه
# بک‌تیک یا * توش داره)، بدون escape ممکنه parse پیام به ادمین رو کلاً
# بشکنه، دقیقاً همون لحظه‌ای که این هشدار بیشترین اهمیت رو داره.
_MARKDOWN_SPECIAL_CHARS = ("`", "*", "_", "[")


def _escape_markdown(text: str) -> str:
    for ch in _MARKDOWN_SPECIAL_CHARS:
        text = text.replace(ch, "\\" + ch)
    return text


def _should_send_alert(key: str) -> bool:
    now = time.monotonic()
    last = _last_alert_at.get(key)
    if last is not None and (now - last) < _ALERT_THROTTLE_SECONDS:
        return False
    _last_alert_at[key] = now
    return True


async def _log_persistent_failure(failure_feature: str | None, user_id: int | None, detail: str):
    if not failure_feature:
        return
    try:
        await feature_usage_repository.log_usage(
            user_id or 0, f"{failure_feature}_failure", detail=detail[:120],
        )
    except Exception as e:
        logger.debug("persistent failure log skipped: %s", e)


async def _record_error_log(error: Exception, traceback_text: str) -> int:
    """رجوع به db/error_log_repository.py برای طراحی کامل — یک ردیف
    به‌ازای هر باگِ یکتا، نه هر رخداد. خروجی ۱ یعنی این اولین بار بود
    (روی هر خطا در ثبتِ خودِ این لاگ — که نباید کل مسیر گزارش خطا رو با
    خودش پایین بکشه — امن به ۱ برمی‌گرده، یعنی رفتار قبل از این تغییر:
    گزارش کامل، بدون فرض ددوپ)."""
    try:
        return await error_log_repository.record_error(
            fingerprint=error_fingerprint.fingerprint_for(error),
            exception_type=type(error).__name__,
            location=error_fingerprint.location_for(error),
            traceback_text=traceback_text[:4000],
        )
    except Exception as e:
        logger.debug("error_log record skipped: %s", e)
        return 1


async def report_error(
    context: ContextTypes.DEFAULT_TYPE,
    error: Exception,
    *,
    context_label: str = "نامشخص",
    failure_feature: str | None = None,
    user_id: int | None = None,
):
    """لاگ + گزارش traceback به ادمین. کاربر عادی هیچ پیامی نمی‌گیرد.

    از این نسخه به بعد، هر رخداد (چه alert واقعی فرستاده بشه چه throttle
    بشه) در error_log ثبت می‌شه — رجوع به db/error_log_repository.py و
    utils/error_fingerprint.py. اگه این *دقیقاً همون* باگیه که قبلاً دیده
    شده (اثرانگشت یکسان)، هم پیام ادمین هم خودِ خط لاگِ فایل فشرده می‌شن
    (بدون traceback تکراری — قبلاً یه‌بار کامل ثبت شده، نه توی فایل که
    سقف ۵MB داره نه در alert) به‌جای این‌که هر تکرار دوباره یه دیوار کامل
    traceback بنویسه/بفرسته."""
    await _log_persistent_failure(failure_feature, user_id, type(error).__name__)

    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    fingerprint = error_fingerprint.fingerprint_for(error)
    occurrence_count = await _record_error_log(error, tb)

    if occurrence_count <= 1:
        # اولین بار — traceback کامل توی فایل لاگ هم لازمه، چون این خودِ
        # تنها نسخه‌ای از این اطلاعاته که تا الان جایی ثبت شده (نسخه‌ی
        # پایدار در error_log هم همین الان، از همین tb، تازه نوشته شد).
        # exc_info=error (نه True): global_error_handler این تابع را از
        # *بیرون* هر بلاک except صدا می‌زند (خودش error handler سطح‌بالای
        # PTB است) — با exc_info=True، لاگینگ از sys.exc_info() می‌خواند
        # که آن‌جا همیشه خالیه، و به‌جای تریسبک واقعی فقط "NoneType: None"
        # ثبت می‌شود (تایید‌شده روی لاگ production واقعی). با پاس دادن
        # مستقیم شیء error، این مشکل نیست — فارغ از این‌که چه چیزی الان
        # "در حال handle شدن" است.
        logger.error("Error in '%s': %s", context_label, error, exc_info=error)
    else:
        # تکراری — traceback کامل از رخداد اول همین الان توی error_log
        # (پایدار، جدا از سقف حجم این فایل) موجوده؛ دوباره نوشتنش توی
        # فایل فقط حجم مصرف می‌کنه بدون اطلاعات جدید، دقیقاً همون چیزی که
        # فایل ۵MB رو زودتر از لازم پر می‌کرد (رجوع به تصمیم ۲/۴ بالای
        # logging_setup.py). یه خط فشرده کافیه.
        logger.warning(
            "DEDUP repeat #%d fp=%s ctx=%s err=%s", occurrence_count, fingerprint, context_label, error,
        )

    if not _should_send_alert(f"{context_label}|{type(error).__name__}"):
        logger.debug("admin alert throttled for %s|%s", context_label, type(error).__name__)
        return

    if occurrence_count <= 1:
        text = (
            f"🚨 **گزارش خطا**\n\n"
            f"**محل:** `{_escape_markdown(context_label)}`\n"
            f"**خطا:** `{_escape_markdown(str(error))}`\n\n"
            f"```\n{tb[:2500]}\n```"
        )
    else:
        # تکراریه — traceback کامل رو (که قبلاً یه‌بار کامل فرستاده شده)
        # دوباره نمی‌فرستیم، فقط این‌که چندمین باره؛ جزئیات کامل همیشه از
        # «🪲 خطاهای اخیر» در پنل ادمین در دسترسه.
        text = (
            f"🚨 **گزارش خطا** (تکراری — {occurrence_count}اُم بار)\n\n"
            f"**محل:** `{_escape_markdown(context_label)}`\n"
            f"**خطا:** `{_escape_markdown(str(error))}`\n"
            f"**اثرانگشت:** `{_escape_markdown(fingerprint)}`\n\n"
            f"جزئیات کامل (نمونه‌ی traceback): «🪲 خطاهای اخیر» در پنل ادمین."
        )
    try:
        await notify_admins(context, text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning("notify_admins failed: %s", e)


async def report_service_issue(
    context: ContextTypes.DEFAULT_TYPE,
    message: str,
    *,
    context_label: str,
    failure_feature: str | None = None,
    user_id: int | None = None,
):
    """هشدار سرویس شناخته‌شده (بدون traceback) فقط به ادمین."""
    logger.warning("Service issue in '%s': %s", context_label, message)

    await _log_persistent_failure(failure_feature, user_id, message[:100])

    if not _should_send_alert(f"{context_label}|svc|{message[:80]}"):
        logger.debug("service alert throttled for %s", context_label)
        return

    text = (
        f"⚠️ **مشکل سرویس**\n\n"
        f"**محل:** `{_escape_markdown(context_label)}`\n"
        f"**پیام:** {_escape_markdown(message[:500])}"
    )
    try:
        await notify_admins(context, text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning("notify_admins failed: %s", e)