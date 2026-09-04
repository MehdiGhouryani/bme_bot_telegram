# src/bme_bot/utils/quiz_archive.py
#
# آرشیو خام سوال‌های تولیدشده‌ی کوییز — یک ردیف JSON در هر خط (JSONL)،
# یک سوال در هر ردیف (نه کل دسته‌ی چندسوالیِ یک تولید در یک ردیف): چون
# استفاده‌ی بعدیِ مدنظر («یه کوییز رندم تو گروه») روی تک‌تک سواله، نه
# لزوماً کل دسته‌ای که یه نفر برای متن دلخواه خودش تولید کرده.
#
# فعلاً فقط نوشتن — عمداً هیچ تابع خواندن/استفاده‌ی مجدد این‌جا نیست
# (طبق تصمیم صریح: «فعلاً فقط ذخیره، بعداً شاید یه بخشی راه بیفته»).
#
# هر ردیف دقیقاً همون schema اعتبارسنجی‌شده‌ی quiz._parse_and_validate_quiz
# را دارد (question/options/correct_index/explanation، از قبل به سقف
# طول واقعی تلگرام truncate شده) + چند فیلد متادیتای اضافه (زمان، کاربر،
# مدل) که ثبتشان همین الان ارزان است ولی بازسازی‌شان بعداً — اگر از اول
# ثبت نشده باشند — ممکن نیست.
#
# نوشتن فایل sync است (io معمولی پایتون) ولی داخل asyncio.to_thread اجرا
# می‌شود تا event loop را برای بقیه‌ی کاربران بلاک نکند؛ یک Lock
# ماژول-level هم از قاطی‌شدن نوشتن‌های هم‌زمان (چند کاربر که تقریباً
# هم‌زمان کوییز می‌سازند) جلوگیری می‌کند.
#
# شکست این تابع هرگز نباید جلوی ارسال واقعی کوییز به کاربر را بگیرد —
# فقط لاگ می‌شود، raise نمی‌کند؛ آرشیو یک کار جانبیِ best-effort است، نه
# بخشی حیاتی از مسیر اصلی فیچر.

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from .. import config

logger = logging.getLogger(__name__)

_write_lock = asyncio.Lock()


def _write_lines_sync(path: str, lines: list[str]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


async def archive_quiz(user_id: int, questions: list[dict], model_used: str) -> None:
    """هر آیتم questions باید دقیقاً همون dict خروجی
    quiz._parse_and_validate_quiz باشد (question/options/correct_index/
    explanation)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    for q in questions:
        entry = {
            "timestamp": now,
            "user_id": user_id,
            "model": model_used,
            "question": q["question"],
            "options": q["options"],
            "correct_index": q["correct_index"],
            "explanation": q["explanation"],
        }
        lines.append(json.dumps(entry, ensure_ascii=False))

    try:
        async with _write_lock:
            await asyncio.to_thread(_write_lines_sync, config.QUIZ_ARCHIVE_PATH, lines)
    except Exception as e:
        logger.error("quiz archive write failed: %s", e)
