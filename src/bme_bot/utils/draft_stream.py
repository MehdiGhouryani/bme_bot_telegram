# src/bme_bot/utils/draft_stream.py
#
# sendRichMessageDraft (Bot API 10.1، ۱۱ ژوئن ۲۰۲۶ — هم‌زمان با
# sendRichMessage معرفی شد؛ رجوع به utils/rich_message.py) پیش‌نمایش تدریجی
# رو این‌بار با فرمت غنی (Rich Markdown) نشون می‌ده، نه متن خام. قبلاً این
# ماژول از sendMessageDraft (Bot API 9.3، همگانی از Bot API 9.5) استفاده
# می‌کرد و *عمداً* plain-text بود — دلیلش این بود که یه prefix ناقص از
# MarkdownV2 استاندارد تقریباً همیشه نامعتبره (escape جفت‌نشده باعث شکست
# کامل parse می‌شه). سینتکس Rich Markdown بخشیدگی بیشتری نسبت به MarkdownV2
# قدیمی داره (دقیقاً همون دلیلی که rich_message.py برای استفاده از
# sendRichMessage در پیام نهایی هم آورده) — پس این محدودیت دیگه صادق نیست و
# می‌شه واقعاً فرمت‌شده (جدول، تیتر، لیست در حال شکل‌گیری) رو تدریجی نشون داد.
#
# نکته‌ی صادقانه که باید گفته بشه: «بخشیدگی بیشتر» به‌معنای «تحمل هر نوع
# برش وسط متنه» نیست — _reveal_steps پایین‌تر هنوز دقیقاً سر جای قبلیش،
# روی موقعیت ثابت کاراکتری برش می‌زنه (نه مثلاً انتهای خط یا بیرون از یک
# جدول نیمه‌کاره)، پس ممکنه بعضی گام‌ها (مثلاً وسط یک جدول در حال تایپ)
# قابل‌parse نباشن. این ریسک عمداً با پیچیدگی بیشتر (مثلاً پیدا کردن نقطه‌ی
# برش «امن») جبران نشده — چون کل این تابع از اول best-effort چندمرحله‌ایه:
# هر خطا (حتی وسط استریم) کل پیش‌نمایش رو بی‌سروصدا لغو می‌کنه و می‌ره سراغ
# پیام نهاییِ واقعی (که مستقل و همیشه کامل ارسال می‌شه) — همون رفتاری که از
# اول بود، فقط حالا احتمال بروزش (نه شدتش) کمی بیشتره. مثل خودِ
# sendMessageDraft، این هم روی محیط تست واقعی تلگرام بررسی نشده (رجوع به
# «نکات باز» در README) — اگه در عمل مزاحم شد، همون AI_STREAMING_ENABLED
# فعلی کافیه برای خاموش کردنش، بدون نیاز به تغییر کد.
#
# محدودیت مهم (تأییدشده برای این متد هم، نه فقط sendMessageDraft قدیمی):
# فقط در چت‌های خصوصی کار می‌کنه، نه گروه/سوپرگروه.
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
# زنده‌ی واقعی مدل» نیست، بلکه «نمایش تدریجیِ پاسخ آماده» است.

import asyncio
import logging

from .. import config

logger = logging.getLogger(__name__)

_DRAFT_ID = 1  # باید non-zero باشه (طبق مستندات)؛ یکتا بودنش per-chat کافیه.
# سقف رسمیِ *مستندشده* برای sendMessageDraft همین ۴۰۹۶ بود؛ مستندات رسمی
# عدد جداگانه‌ای برای sendRichMessageDraft اعلام نکرده (برخلاف
# sendRichMessage که صراحتاً ۳۲۷۶۸ گفته شده — رجوع به rich_message.py). چون
# اینجا فقط یه *پیش‌نمایش* کوتاهه (نه پیام نهایی)، سقف محافظه‌کارانه‌ی قبلی
# رو دست نزدیم — عمداً کمتر نگه‌داشتنش از هر سقف واقعی (هرچی باشه) کاملاً
# بی‌خطره، فقط ممکنه پیش‌نمایش زودتر از حد لازم قطع بشه، نه این‌که رد بشه.
_MAX_DRAFT_CHARS = 4096
_TARGET_STEPS = 12
_MIN_CHUNK_CHARS = 40
_STEP_DELAY_SECONDS = 0.4  # کل نمایش برای متن متوسط چندثانیه طول می‌کشه — خیلی کمتر از سقف ۳۰ثانیه‌ای draft.


def _reveal_steps(full_text: str) -> list[str]:
    """full_text رو به یه دنباله از prefix های تجمعیِ فزاینده تقسیم
    می‌کنه، برای نمایش گام‌به‌گام draft. روی متن‌های خیلی طولانی، فقط تا
    سقف _MAX_DRAFT_CHARS پیش‌نمایش نشون داده می‌شه (رجوع به توضیح این
    ثابت بالای فایل برای این‌که این سقف دقیقاً از کجا میاد) — پیام نهایی
    واقعی (که این ماژول مسئولش نیست) کامل و بدون این محدودیت ارسال می‌شه."""
    capped = full_text[:_MAX_DRAFT_CHARS]
    if len(capped) <= _MIN_CHUNK_CHARS:
        return [capped] if capped else []

    step_size = max(_MIN_CHUNK_CHARS, -(-len(capped) // _TARGET_STEPS))  # ceil division
    steps = [capped[:end] for end in range(step_size, len(capped), step_size)]
    steps.append(capped)
    return steps


async def stream_preview(bot, chat_id: int, full_text: str, is_private_chat: bool) -> bool:
    """پیش‌نمایش تدریجی full_text رو به‌عنوان یه rich-markdown draft نشون
    می‌ده. روی موفقیت کامل True برمی‌گردونه (فراخواننده هنوز باید
    sendMessage/_send_reply_chunks نهایی رو خودش بفرسته — این تابع فقط
    پیش‌نمایشه). روی هر مانع — چت گروهی (sendRichMessageDraft هم فقط
    خصوصیه)، فلگ config خاموش، یا هر خطای واقعی API (حتی غیرمنتظره،
    شامل یه گامِ میانی که به‌خاطر برش وسط یه ساختار Rich Markdown نامعتبر
    از آب دراومده) — بی‌سروصدا False برمی‌گردونه تا فراخواننده فوراً و
    خودکار به روش قدیمی (فقط ارسال یک‌جای پیام نهایی، بدون پیش‌نمایش)
    برگرده.

    برخلاف utils/rich_message.py، هر گام این‌جا (عمداً) با async_retry
    دوباره تلاش نمی‌کنه: کل این تابع خودش یک مکانیزم best-effort چندمرحله‌ایه
    (۱۲ گام سبک، نه یک پیام حیاتی تک‌مرحله‌ای) — retry کردن تک‌تک گام‌ها هم
    پیچیدگی اضافه می‌کنه هم با تاخیرش می‌تونه به سقف ۳۰ثانیه‌ای انقضای
    draft نزدیک‌تر بشه؛ هر شکستی (حتی گذرا یا صرفاً یه گام میانی نامعتبر)
    به‌سادگی کل پیش‌نمایش رو لغو می‌کنه و می‌ره سراغ پیام نهایی، که همیشه
    درست کار می‌کنه.
    """
    if not is_private_chat or not config.AI_STREAMING_ENABLED:
        return False

    steps = _reveal_steps(full_text)
    if not steps:
        return False

    try:
        for i, partial_text in enumerate(steps):
            await bot.do_api_request(
                "sendRichMessageDraft",
                {"chat_id": chat_id, "draft_id": _DRAFT_ID, "rich_message": {"markdown": partial_text}},
            )
            if i < len(steps) - 1:
                # بعد از آخرین گام مکث نمی‌کنیم — فراخواننده بلافاصله
                # پیام نهایی رو می‌فرسته، صبر اضافه بعد از آخرین پیش‌نمایش
                # فقط تاخیر بی‌فایده‌ست.
                await asyncio.sleep(_STEP_DELAY_SECONDS)
        return True
    except Exception as e:
        logger.info("ai_assistant rich draft streaming failed, falling back: %s", e)
        return False
