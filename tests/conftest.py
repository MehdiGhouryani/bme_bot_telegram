# tests/conftest.py
#
# error_reporting._last_alert_at یک دیکشنری ماژول-level
# است (throttle هشدارهای تکراری، عمداً in-memory). چون بین توابع تست در یک
# session پابرجا می‌ماند، بدون ریست یک تست می‌تواند به‌اشتباه تستِ بعدی از
# خودش را throttle کند (اگر context_label+نوع خطا یکسان باشد) — یک فیکسچر
# autouse قبل از هر تست آن را خالی می‌کند تا هر تست کاملاً مستقل بماند.

import pytest


@pytest.fixture(autouse=True)
def _reset_alert_throttle():
    from bme_bot.utils import error_reporting

    error_reporting._last_alert_at.clear()
    yield
