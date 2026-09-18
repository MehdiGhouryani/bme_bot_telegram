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
import os
import random
from datetime import datetime, timezone

from .. import config

logger = logging.getLogger(__name__)

_write_lock = asyncio.Lock()


def _write_lines_sync(path: str, lines: list[str]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


# کلیدهای الزامی برای این‌که یک ردیف آرشیو مستقیماً قابل تحویل به
# context.bot.send_poll باشد — همان چهار فیلدی که archive_quiz بالا از
# quiz._parse_and_validate_quiz دریافت و ذخیره می‌کند.
_REQUIRED_QUESTION_KEYS = ("question", "options", "correct_index", "explanation")


def _read_random_line_sync(path: str) -> dict | None:
    """کل فایل را می‌خواند و یک ردیفِ معتبر و تصادفی برمی‌گرداند.

    این تابع sync است (دقیقاً مثل _write_lines_sync بالا) و باید فقط از
    طریق asyncio.to_thread صدا زده شود تا event loop را برای بقیه‌ی
    کاربران بلاک نکند.

    خواندن کل فایل در حافظه (به‌جای reservoir sampling بدون بارگذاری کل
    فایل) یک تصمیم آگاهانه است: هر ردیف آرشیو چند صد بایت است و حتی چند
    ده‌هزار ردیف هم چند مگابایت بیشتر نمی‌شود — برای این حجم، سادگی این
    روش بر بهینه‌سازی زودهنگام ارجحیت دارد. اگر آرشیو زمانی به مقیاسی
    رسید که این فرض دیگر درست نبود، این تابع باید بازبینی شود.

    ردیف‌های خراب/ناقص (مثلاً یک خط JSON نامعتبر از یک نوشتن قطع‌شده، یا
    یک schema قدیمی‌تر که یکی از فیلدهای لازم را ندارد) به‌جای متوقف‌کردن
    کل عملیات فقط لاگ و رد می‌شوند — یک ردیف بد نباید مانع استفاده از
    بقیه‌ی آرشیو شود.
    """
    if not os.path.exists(path):
        return None

    valid_entries: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                logger.warning("quiz archive: line %d is not valid JSON, skipping", line_number)
                continue
            if not isinstance(entry, dict) or not all(k in entry for k in _REQUIRED_QUESTION_KEYS):
                logger.warning("quiz archive: line %d missing required keys, skipping", line_number)
                continue
            valid_entries.append(entry)

    if not valid_entries:
        return None
    return random.choice(valid_entries)


async def get_random_question() -> dict | None:
    """یک سوال تصادفی از آرشیو برمی‌گرداند، یا None اگر آرشیو هنوز وجود
    ندارد/خالی است/هیچ ردیف معتبری ندارد. خروجی دقیقاً همان شکل dict
    ورودیِ questions در archive_quiz (question/options/correct_index/
    explanation) به‌علاوه‌ی متادیتای اضافه (timestamp/user_id/model) است
    که فراخواننده باید نادیده بگیرد."""
    return await asyncio.to_thread(_read_random_line_sync, config.QUIZ_ARCHIVE_PATH)


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
