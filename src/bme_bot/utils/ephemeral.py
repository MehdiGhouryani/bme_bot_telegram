# src/bme_bot/utils/ephemeral.py
#
# Ephemeral Messages (Bot API 10.2، ۱۴ جولای ۲۰۲۶) امکان می‌ده بات یه پیام
# رو داخل یه گروه/سوپرگروه بفرسته که فقط یه کاربر مشخص (و خودِ بات) اون رو
# می‌بینه، نه بقیه‌ی اعضا — دقیقاً همون قابلیتی که امکان می‌ده فیچرهای
# «فقط چت خصوصی» رو بدون شلوغ‌کردن گروه برای بقیه، داخل گروه هم باز کنیم.
#
# این یه فیلد جدید (receiver_user_id) روی متدهای ارسال *موجود*ه (sendMessage
# و مشابه‌هاش)، نه یه متد کاملاً جدید — پس برخلاف utils/rich_message.py و
# utils/draft_stream.py (که هردو do_api_request برای متدهای کاملاً جدید
# استفاده می‌کنن)، این‌جا دقیقاً همون الگوی utils/button_style.py و
# utils/date_time_entity.py به کار می‌ره: api_kwargs روی متد typed موجود
# (bot.send_message). تأیید شده مستقیم با
# inspect.signature(telegram.Bot.send_message) که api_kwargs رو به‌عنوان
# پارامتر رسمی خودِ python-telegram-bot==21.4 (نه چیزی مخصوص این پروژه)
# می‌شناسه؛ محتواش مستقیم داخل JSON درخواست HTTP نهایی merge می‌شه.
#
# محدودیت‌های شناخته‌شده (طبق مستندات رسمی؛ رجوع به «نکات باز» در README
# برای الگوی مشابه با sendMessageDraft — این هم با یه بات/گروه واقعی
# تلگرام تست نشده):
# - receiver_user_id باید عضو همون چت باشه — طبیعتاً همیشه صادقه چون
#   کاربر همین الان داخل همون گروه پیامی فرستاده که ما داریم بهش جواب
#   می‌دیم.
# - فقط برای *ارسال* پیام تازه‌ست، نه ویرایش پیام‌های قبلاً ارسال‌شده —
#   برای اون، متدهای جداگانه‌ای مثل editEphemeralMessageText لازمه که این
#   پروژه (عمداً، برای نسخه‌ی اول محتاطانه) پیاده نکرده.
# - این قابلیت خیلی تازه‌ست (Bot API 10.2 دو ماه پیش)؛ به همین دلیل
#   send_or_fallback پایین‌تر هر شکستی رو با یه پیام معمولیِ قابل‌دیدن
#   برای همه جبران می‌کنه — چون نرسوندن جواب بدتر از دیده‌شدنش توسط بقیه‌ی
#   گروهه.

import logging

logger = logging.getLogger(__name__)


def to_kwargs(user_id: int) -> dict:
    """خروجی رو مستقیم به‌عنوان api_kwargs به send_message (یا هر متد
    ارسال typed مشابه) پاس بده تا فقط user_id بتونه پیام رو ببینه:
    await bot.send_message(..., api_kwargs=ephemeral.to_kwargs(user_id))"""
    return {"receiver_user_id": user_id}


async def send_or_fallback(send_fn, *, chat_id: int, user_id: int, **send_kwargs) -> bool:
    """send_fn معمولاً context.bot.send_message است (یا هر متد ارسال typed
    دیگه‌ای با همون امضای api_kwargs). اول یه تلاش ephemeral (فقط user_id
    می‌بینه) می‌زنه؛ روی هر خطای واقعی API، بی‌صدا با همون chat_id/kwargs
    ولی *بدون* api_kwargs ephemeral (یعنی پیام معمولی و قابل‌دیدن برای کل
    چت) دوباره تلاش می‌کنه — پیام در هر دو حالت واقعاً ارسال می‌شه، فقط
    دامنه‌ی دیده‌شدنش فرق می‌کنه.

    خروجی True یعنی مسیر ephemeral جواب داد، False یعنی از fallback عادی
    استفاده شد."""
    try:
        await send_fn(chat_id=chat_id, api_kwargs=to_kwargs(user_id), **send_kwargs)
        return True
    except Exception as e:
        logger.info("ephemeral send failed, falling back to a normal group-visible reply: %s", e)
        await send_fn(chat_id=chat_id, **send_kwargs)
        return False
