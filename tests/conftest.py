# tests/conftest.py
#
# error_reporting._last_alert_at یک دیکشنری ماژول-level
# است (throttle هشدارهای تکراری، عمداً in-memory). چون بین توابع تست در یک
# session پابرجا می‌ماند، بدون ریست یک تست می‌تواند به‌اشتباه تستِ بعدی از
# خودش را throttle کند (اگر context_label+نوع خطا یکسان باشد) — یک فیکسچر
# autouse قبل از هر تست آن را خالی می‌کند تا هر تست کاملاً مستقل بماند.
#
# utils.admin._dynamic_admin_ids دقیقاً همین مشکل را دارد (هم عمداً
# ماژول-level برای اینکه is_admin() sync و ارزان بماند — رجوع به کامنت آنجا)
# — یک تست که add_dynamic_admin صدا می‌زند، بدون ریست می‌تواند تست بعدی را
# (که فرض می‌کند هیچ ادمین دینامیکی نیست) خراب کند.

import pytest


@pytest.fixture(autouse=True)
def _reset_alert_throttle():
    from bme_bot.utils import error_reporting

    error_reporting._last_alert_at.clear()
    yield


@pytest.fixture(autouse=True)
def _reset_dynamic_admins():
    from bme_bot.utils import admin as admin_utils

    admin_utils._dynamic_admin_ids.clear()
    yield
    admin_utils._dynamic_admin_ids.clear()
