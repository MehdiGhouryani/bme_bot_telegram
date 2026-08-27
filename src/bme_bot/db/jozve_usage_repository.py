# src/bme_bot/db/jozve_usage_repository.py
#
# محدودیت روزانه و کول‌داون فیچر «ویس استاد به جزوه». سقف از جدول
# feature_limits خوانده می‌شود و از پنل ادمین قابل‌تغییر است (پیش‌فرض seed
# ۱/روز — عمداً سخت‌گیرانه‌تر از ai/ocr/quiz، چون سقف توکن روزانه‌ی fallback
# مشترک Groq بین همه‌ی فیچرهای AI-محور محدوده؛ رجوع به README.md). پیاده‌سازی
# SQL در db/usage_limit_helper.py است (بین این فایل و ai/ocr/quiz مشترک).

from typing import Tuple

from . import usage_limit_helper

_TABLE_NAME = "jozve_usage"
_FEATURE_NAME = "jozve"


async def check_jozve_limit(user_id: int) -> Tuple[bool, str]:
    return await usage_limit_helper.check_limit(_TABLE_NAME, _FEATURE_NAME, user_id)


async def record_attempt(user_id: int) -> None:
    await usage_limit_helper.record_attempt(_TABLE_NAME, user_id)


async def increment_jozve_usage(user_id: int) -> None:
    await usage_limit_helper.increment_usage(_TABLE_NAME, user_id)
