# src/bme_bot/utils/error_reporting.py
# لاگ + گزارش خطا به ادمین (با throttle). هرگز به کاربر عادی پیام نمی‌فرستد.

from __future__ import annotations

import logging
import time
import traceback

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .admin import notify_admins
from ..db import feature_usage_repository

logger = logging.getLogger(__name__)

_ALERT_THROTTLE_SECONDS = 600
_last_alert_at: dict[str, float] = {}


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


async def report_error(
    context: ContextTypes.DEFAULT_TYPE,
    error: Exception,
    *,
    context_label: str = "نامشخص",
    failure_feature: str | None = None,
    user_id: int | None = None,
):
    """لاگ + گزارش traceback به ادمین. کاربر عادی هیچ پیامی نمی‌گیرد."""
    logger.error("Error in '%s': %s", context_label, error, exc_info=True)

    await _log_persistent_failure(failure_feature, user_id, type(error).__name__)

    if not _should_send_alert(f"{context_label}|{type(error).__name__}"):
        logger.debug("admin alert throttled for %s|%s", context_label, type(error).__name__)
        return

    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    text = (
        f"🚨 **گزارش خطا**\n\n"
        f"**محل:** `{context_label}`\n"
        f"**خطا:** `{error}`\n\n"
        f"```\n{tb[:2500]}\n```"
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
        f"**محل:** `{context_label}`\n"
        f"**پیام:** {message[:500]}"
    )
    try:
        await notify_admins(context, text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning("notify_admins failed: %s", e)