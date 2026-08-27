# src/bme_bot/db/ocr_usage_repository.py
#
# محدودیت روزانه و کول‌داون فیچر OCR. سقف از جدول feature_limits خوانده
# می‌شود و از پنل ادمین قابل‌تغییر است. پیاده‌سازی SQL در
# db/usage_limit_helper.py است (بین این فایل و ai/quiz/jozve مشترک).

from typing import Tuple

from . import usage_limit_helper

_TABLE_NAME = "ocr_usage"
_FEATURE_NAME = "ocr"


async def check_ocr_limit(user_id: int) -> Tuple[bool, str]:
    return await usage_limit_helper.check_limit(_TABLE_NAME, _FEATURE_NAME, user_id)


async def record_attempt(user_id: int) -> None:
    await usage_limit_helper.record_attempt(_TABLE_NAME, user_id)


async def increment_ocr_usage(user_id: int) -> None:
    await usage_limit_helper.increment_usage(_TABLE_NAME, user_id)
