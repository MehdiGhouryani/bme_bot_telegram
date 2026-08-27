# src/bme_bot/db/ai_usage_repository.py
#
# محدودیت روزانه و کول‌داون سوال از هوش مصنوعی. سقف از جدول feature_limits
# خوانده می‌شود (db/feature_limits_repository.py) و از پنل ادمین قابل‌تغییر
# است. پیاده‌سازی SQL در db/usage_limit_helper.py است (بین این فایل و
# ocr/quiz/jozve مشترک).

from typing import Tuple

from . import usage_limit_helper

_TABLE_NAME = "ai_usage"
_FEATURE_NAME = "ai"


async def check_ai_limit(user_id: int) -> Tuple[bool, str]:
    return await usage_limit_helper.check_limit(_TABLE_NAME, _FEATURE_NAME, user_id)


async def record_attempt(user_id: int) -> None:
    await usage_limit_helper.record_attempt(_TABLE_NAME, user_id)


async def increment_ai_usage(user_id: int) -> None:
    await usage_limit_helper.increment_usage(_TABLE_NAME, user_id)
