# src/bme_bot/utils/draft_stream.py
#
# sendMessageDraft (Bot API 9.3، متاح برای همه‌ی بات‌ها از Bot API 9.5،
# اول مارس ۲۰۲۶) امکان نمایش پیش‌نمایش تدریجی («در حال تایپ») یک پیام قبل
# از نهایی‌شدنش رو می‌ده. طبق مستندات رسمی، draft یه پیش‌نمایش موقتِ حداکثر
# ۳۰ثانیه‌ای است و هیچ‌وقت خودش پیام واقعی نمی‌شه — بعد از تمام‌شدن باید
# sendMessage با متن کامل صدا زده بشه تا واقعاً در چت ذخیره بشه (این تابع
# فقط پیش‌نمایش رو مدیریت می‌کنه؛ ارسال پیام نهایی برعهده‌ی فراخواننده‌ست).
#
# محدودیت مهم: طبق مستندات، فقط در چت‌های خصوصی کار می‌کنه، نه گروه/سوپرگروه.
#
# python-telegram-bot==21.4 (نسخه‌ی pin‌شده‌ی این پروژه) متد typed برای این
# نداره چون این متد HTTP کاملاً بعد از انتشار اون نسخه اضافه شده — از
# bot.do_api_request استفاده می‌کنیم (رجوع به توضیح مشابه در
# utils/rich_message.py).
#
# ai_service.ask() یک تماس معمولی (غیر-استریم) است — کل پاسخ AI یک‌جا از
# لیت‌الایام برمی‌گرده، نه توکن‌به‌توکن. عمداً این معماری رو دست نزدیم (این
# سرویس بین سه فیچر مشترکه: ai_assistant/quiz/jozve، و منطق چندلایه‌ی
# fallback بین مدل‌هاش به‌شدت تست‌شده و حساسه — بازنویسیش برای پشتیبانی از
# استریم واقعی توکن‌به‌توکن ریسک رگرشن بزرگی داره که با هدف این تغییر
# (بهبود UI) اصلاً تناسب نداره). به‌جاش، بعد از رسیدن پاسخ کامل، به‌شکل
# تدریجی (چند گام فزاینده) به‌عنوان draft نمایش داده می‌شه — یعنی «تایپ
# زنده‌ی واقعی مدل» نیست، بلکه «نمایش تدریجیِ پاسخ آماده» است؛ از نظر
# کاربر تفاوت محسوسی نداره چون هردو حالت متن رو تکه‌تکه و فزاینده می‌بینه.

import asyncio
import logging

from .. import config

logger = logging.getLogger(__name__)

_DRAFT_ID = 1  # باید non-zero باشه (طبق مستندات)؛ یکتا بودنش per-chat کافیه.
_MAX_DRAFT_CHARS = 4096  # سقف رسمی sendMessageDraft.
_TARGET_STEPS = 12
_MIN_CHUNK_CHARS = 40
_STEP_DELAY_SECONDS = 0.4  # کل نمایش برای متن متوسط چندثانیه طول می‌کشه — خیلی کمتر از سقف ۳۰ثانیه‌ای draft.


def _reveal_steps(full_text: str) -> list[str]:
    """full_text رو به یه دنباله از prefix های تجمعیِ فزاینده تقسیم
    می‌کنه، برای نمایش گام‌به‌گام draft. روی متن‌های خیلی طولانی، فقط تا
    سقف ۴۰۹۶ کاراکتر (سقف خودِ sendMessageDraft) پیش‌نمایش نشون داده
    می‌شه — پیام نهایی واقعی (که این ماژول مسئولش نیست) کامل و بدون این
    محدودیت ارسال می‌شه."""
    capped = full_text[:_MAX_DRAFT_CHARS]
    if len(capped) <= _MIN_CHUNK_CHARS:
        return [capped] if capped else []

    step_size = max(_MIN_CHUNK_CHARS, -(-len(capped) // _TARGET_STEPS))  # ceil division
    steps = [capped[:end] for end in range(step_size, len(capped), step_size)]
    steps.append(capped)
    return steps


async def stream_preview(bot, chat_id: int, full_text: str, is_private_chat: bool) -> bool:
    """پیش‌نمایش تدریجی full_text رو به‌عنوان یه draft نشون می‌ده. روی
    موفقیت کامل True برمی‌گردونه (فراخواننده هنوز باید sendMessage نهایی
    رو خودش بفرسته — این تابع فقط پیش‌نمایشه). روی هر مانع — چت گروهی
    (sendMessageDraft فقط خصوصیه)، فلگ config خاموش، یا هر خطای واقعی API
    (حتی غیرمنتظره) — بی‌سروصدا False برمی‌گردونه تا فراخواننده فوراً و
    خودکار به روش قدیمی (فقط ارسال یک‌جای پیام نهایی، بدون پیش‌نمایش)
    برگرده. متن پیش‌نمایش عمداً plain-text است، بدون parse_mode: یه
    prefix ناقص از متن فرمت‌شده (مثلاً "**نیمه‌کاره) تقریباً همیشه
    MarkdownV2 نامعتبره و باعث شکست هر گام می‌شه — فرمت کامل و درست فقط
    در پیام نهاییِ persist‌شده اعمال می‌شه، نه در این پیش‌نمایش گذرا.

    برخلاف utils/rich_message.py، هر گام این‌جا (عمداً) با async_retry
    دوباره تلاش نمی‌کنه: کل این تابع خودش یک مکانیزم best-effort چندمرحله‌ایه
    (۱۲ گام سبک، نه یک پیام حیاتی تک‌مرحله‌ای) — retry کردن تک‌تک گام‌ها هم
    پیچیدگی اضافه می‌کنه هم با تاخیرش می‌تونه به سقف ۳۰ثانیه‌ای انقضای
    draft نزدیک‌تر بشه؛ هر شکستی (حتی گذرا) به‌سادگی کل پیش‌نمایش رو لغو
    می‌کنه و می‌ره سراغ پیام نهایی، که همیشه درست کار می‌کنه.
    """
    if not is_private_chat or not config.AI_STREAMING_ENABLED:
        return False

    steps = _reveal_steps(full_text)
    if not steps:
        return False

    try:
        for i, partial_text in enumerate(steps):
            await bot.do_api_request(
                "sendMessageDraft",
                {"chat_id": chat_id, "draft_id": _DRAFT_ID, "text": partial_text},
            )
            if i < len(steps) - 1:
                # بعد از آخرین گام مکث نمی‌کنیم — فراخواننده بلافاصله
                # پیام نهایی رو می‌فرسته، صبر اضافه بعد از آخرین پیش‌نمایش
                # فقط تاخیر بی‌فایده‌ست.
                await asyncio.sleep(_STEP_DELAY_SECONDS)
        return True
    except Exception as e:
        logger.info("ai_assistant draft streaming failed, falling back: %s", e)
        return False
