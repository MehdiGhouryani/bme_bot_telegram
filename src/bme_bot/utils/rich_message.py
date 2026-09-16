# src/bme_bot/utils/rich_message.py
#
# sendRichMessage (Bot API 10.1، ۱۱ ژوئن ۲۰۲۶) به بات‌ها اجازه می‌ده پیام‌ها
# رو با فرمت غنی (جدول، تیتر، لیست تودرتو، بلوک کد، quote تاشو) مستقیم تو
# چت بفرستن — بدون نیاز به escape کردن دستی MarkdownV2 (سینتکس Rich
# Markdown با MarkdownV2 قدیمی یکی نیست و بخشیدگی بیشتری نسبت به خروجی خام
# مدل‌های AI داره). این یه متد HTTP کاملاً جدیده، نه فقط یه فیلد اضافه روی
# متد قدیمی — یعنی python-telegram-bot==21.4 (نسخه‌ی pin‌شده‌ی این پروژه،
# از قبل از این تاریخ) هیچ متد typed برایش نداره. از bot.do_api_request
# استفاده می‌کنیم — راه رسمی خودِ PTB برای متدهای جدیدتر از نسخه‌ی نصب‌شده
# (مستندش رو مستقیم از سورس نصب‌شده خوندیم، نه حدس).
#
# سقف‌های sendRichMessage: حداکثر ۳۲۷۶۸ کاراکتر UTF-8 و ۵۰۰ بلاک. شمردن
# دقیق تعداد بلاک از روی متن خام Markdown عملی نیست، پس فقط روی طول بایت
# چک می‌کنیم و اگه خود API به هر دلیل دیگه (مثلاً تعداد بلاک) رد کنه،
# همون except پایین گرفته می‌شه — رفتار امن یکسانه.

import logging

from .retry import async_retry

logger = logging.getLogger(__name__)

# سقف رسمی sendRichMessage. اگه محتوا از این بیشتر بود، اصلاً تلاش نمی‌کنیم
# (خطای رد قطعی API رو جلو می‌گیریم) — فراخواننده باید مسیر جایگزین
# (مثلاً فایل) رو بدون قید و شرط اجرا کنه.
RICH_MESSAGE_MAX_BYTES = 32768


async def send_rich_message(bot, chat_id, markdown_text: str, **extra) -> bool:
    """پیام را با sendRichMessage (حالت markdown) ارسال می‌کند. روی موفقیت
    True، روی هر خطای واقعی تلگرام (یا محتوای بیش از سقف مجاز) False
    برمی‌گرداند — نه exception — چون این تابع همیشه باید یک قابلیت
    «اضافه»/best-effort باشد: فراخواننده در صورت False باید بی‌سروصدا به
    روش قبلی (که همیشه کار کرده) برگردد، نه این‌که کل جریان کاربر بشکند.

    extra کلیدهای اضافی سطح بالای درخواست (مثل reply_parameters) است، نه
    داخل خودِ rich_message.
    """
    if len(markdown_text.encode("utf-8")) > RICH_MESSAGE_MAX_BYTES:
        logger.info("send_rich_message: content exceeds %d bytes, skipping", RICH_MESSAGE_MAX_BYTES)
        return False

    async def _call():
        return await bot.do_api_request(
            "sendRichMessage",
            {"chat_id": chat_id, "rich_message": {"markdown": markdown_text}, **extra},
        )

    try:
        await async_retry(_call, label="send_rich_message")
        return True
    except Exception as e:
        # عمداً Exception عام، نه فقط TelegramError: این تابع یک قابلیت
        # کاملاً افزوده و best-effort است (فراخواننده‌ها همیشه یک مسیر
        # جایگزینِ همیشه-کارکرده دارند) — هیچ خطای غیرمنتظره‌ای از این‌جا
        # نباید جریان اصلی کاربر را بشکند.
        logger.info("send_rich_message failed, caller should fall back: %s", e)
        return False


async def edit_rich_message(
    bot, chat_id, message_id, markdown_text: str, reply_markup=None, **extra,
) -> bool:
    """ادیت درجای یه پیام موجود با Rich Markdown.

    برخلاف sendRichMessage (متد کاملاً جدا)، اینجا از همون پارامتر
    `rich_message` روی editMessageText استفاده می‌کنیم که در همون آپدیت Bot
    API 10.1 اضافه شده («Added the parameter rich_message to the method
    editMessageText, allowing bots to edit rich messages» — core.telegram.org
    changelog) — یعنی برخلاف فرض اولیه، نیازی به حذف+ارسال دوباره‌ی پیام
    نیست، می‌شه همون پیام موجود رو مستقیم ادیت کرد.

    توجه: editMessageCaption همچین پارامتری نگرفته — پس این تابع فقط برای
    پیام‌های متنی کاربرد داره، نه کپشن عکس (اکشن definition همچنان باید از
    edit_message_caption معمولی با Markdown قدیمی استفاده کنه).

    همون الگوی امن send_rich_message: True/False، نه exception — فراخواننده
    روی False باید بی‌صدا به روش قبلی (edit_message_text با
    parse_mode=Markdown) برگرده."""
    if len(markdown_text.encode("utf-8")) > RICH_MESSAGE_MAX_BYTES:
        logger.info("edit_rich_message: content exceeds %d bytes, skipping", RICH_MESSAGE_MAX_BYTES)
        return False

    payload = {"chat_id": chat_id, "message_id": message_id, "rich_message": {"markdown": markdown_text}, **extra}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    async def _call():
        return await bot.do_api_request("editMessageText", payload)

    try:
        await async_retry(_call, label="edit_rich_message")
        return True
    except Exception as e:
        # همون منطق send_rich_message: قابلیت افزوده و best-effort، فراخواننده
        # همیشه یک مسیر جایگزینِ همیشه-کارکرده دارد.
        logger.info("edit_rich_message failed, caller should fall back: %s", e)
        return False
