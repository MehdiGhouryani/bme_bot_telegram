# src/bme_bot/utils/entities_to_markdown.py
#
# مشکل واقعی: وقتی ادمین تو تلگرام با فرمت‌دهی حین تایپ (دکمه‌ی B/I یا
# میانبر صفحه‌کلید) می‌نویسه، خودِ کلاینت تلگرام کاراکترهای */** رو از متن
# حذف می‌کنه و به‌جاش یه MessageEntity واقعی (bold/italic/code/...) به پیام
# می‌چسبونه. یعنی update.message.text دیگه شامل این کاراکترها نیست — فقط تو
# update.message.entities هست. اگه فقط .text ذخیره بشه، فرمت ادمین بی‌صدا
# از بین می‌ره (نه خطا) — چون کلاینت‌های تلگرام (موبایل/دسکتاپ) این کار رو
# صرف‌نظر از این‌که کاربر «فرمت‌دهی حین تایپ» رو دستی خاموش کرده یا نه، روی
# متن‌های تایپ‌شده با آیکون/میانبر انجام می‌دن.
#
# این تابع دقیقاً عکسِ کاری که کلاینت تلگرام انجام داد رو می‌کنه: entity ها
# رو به سینتکس Markdown برمی‌گردونه. بخش‌هایی از متن که entity ندارن (مثل
# ##/### تیتر یا - بولت که ادمین *دستی* تایپ کرده، چون تلگرام entity ای
# برای این‌ها نداره) کاملاً دست‌نخورده باقی می‌مونن — این تابع escape
# نمی‌کنه، چون این کاراکترها رو خودِ ادمین آگاهانه به‌عنوان سینتکس تایپ کرده.
#
# --- نکته‌ی حیاتی: دو فلیور، دو سینتکس متفاوت برای بولد/ایتالیک ---
# «معرفی» دستگاه (کپشن عکس) با ParseMode.MARKDOWN قدیمی (Bot API V1) نشون
# داده می‌شه که توش بولد یه ستاره‌ی تکی (*بولد*) و ایتالیک زیرخط
# (_ایتالیک_) هست؛ بقیه‌ی فیلدها با Rich Markdown (sendRichMessage/
# editMessageText+rich_message، Bot API 10.1) نشون داده می‌شن که سبک
# CommonMark داره: بولد دو-ستاره (**بولد**)، ایتالیک تک‌ستاره (*ایتالیک*).
# اگه فلیور اشتباه انتخاب بشه (مثلاً دو-ستاره تو کپشن legacy)، تلگرام یا
# غلط رندر می‌کنه یا رد می‌کنه — پس flavor باید دقیقاً با parse mode واقعیِ
# مقصد یکی باشه؛ راهنما در FLAVOR_RICH / FLAVOR_LEGACY.
#
# legacy علاوه بر این strikethrough رو اصلاً پشتیبانی نمی‌کنه (Bot API V1
# محدوده) — اگه چنین entity ای برسه، به‌جای تزریق سینتکس نامعتبر، wrapper
# اصلاً اضافه نمی‌شه (متن ساده باقی می‌مونه، فقط سبکش از دست می‌ره، نه کل پیام).
#
# نکته‌ی UTF-16: MessageEntity.offset/length بر پایه‌ی UTF-16 code unit
# هستن (همون نکته‌ی utils/text_chunking.py، اینجا هم صدق می‌کنه) نه ایندکس
# کاراکتر پایتون؛ بدون تبدیل، متن‌های حاوی ایموجی خارج از BMP غلط برش
# می‌خورن.

from __future__ import annotations

from telegram import MessageEntity

FLAVOR_RICH = "rich"
FLAVOR_LEGACY = "legacy"

_WRAPPERS = {
    FLAVOR_RICH: {
        MessageEntity.BOLD: "**",
        MessageEntity.ITALIC: "*",
        MessageEntity.CODE: "`",
        MessageEntity.STRIKETHROUGH: "~~",
    },
    FLAVOR_LEGACY: {
        MessageEntity.BOLD: "*",
        MessageEntity.ITALIC: "_",
        MessageEntity.CODE: "`",
        # STRIKETHROUGH عمداً غایب: Markdown قدیمی (V1) اصلاً همچین
        # سینتکسی نداره.
    },
}


def _build_unit_to_char_index(text: str) -> list[int]:
    """نگاشت هر واحد UTF-16 به ایندکس کاراکتر پایتونِ نگه‌دارنده‌اش —
    کاراکترهای خارج از BMP (۲ واحد UTF-16، ۱ کاراکتر پایتون) هر دو واحدشون
    به همون یک ایندکس نگاشت می‌شن. یک ورودی اضافه در انتها برای offset+length
    ای که دقیقاً به انتهای متن می‌رسه."""
    mapping: list[int] = []
    for i, ch in enumerate(text):
        mapping.extend([i] * (2 if ord(ch) > 0xFFFF else 1))
    mapping.append(len(text))
    return mapping


def entities_to_markdown(text: str | None, entities, flavor: str = FLAVOR_RICH) -> str:
    """متن خام + entities تلگرام رو به یه رشته‌ی Markdown (سبک flavor)
    تبدیل می‌کنه که فرمت‌دهی زنده‌ی ادمین رو با سینتکس صریح نشون می‌ده.

    الگوریتم تک‌پاس (نه insert های متوالی روی همون لیست): برای هر span یه
    رویداد «باز شدن» رو ایندکس start و یه رویداد «بسته شدن» رو ایندکس end
    ثبت می‌کنیم، بعد متن رو یک‌بار از اول تا آخر می‌خونیم و قبل از هر
    کاراکتر، اول wrapper های بسته‌شونده‌ی همون موقعیت (تودرتوترین اول — LIFO)
    و بعد wrapper های بازشونده (بیرونی‌ترین اول) رو اضافه می‌کنیم. این روش،
    برخلاف insert متوالی روی یه لیست، از جابه‌جایی offset ها وقتی چند span
    تو در تو با start/end متفاوت دارن (نه فقط start مشترک) رنج نمی‌بره —
    چون همه‌چیز از روی ایندکس‌های *اصلی* متن محاسبه می‌شه، نه لیستِ در حال
    تغییر."""
    if not text:
        return text or ""
    if not entities:
        return text

    wrappers = _WRAPPERS[flavor]
    relevant = [e for e in entities if e.type in wrappers]
    if not relevant:
        return text

    unit_to_char = _build_unit_to_char_index(text)
    last_index = len(unit_to_char) - 1

    spans = []
    for e in relevant:
        start = unit_to_char[min(e.offset, last_index)]
        end = unit_to_char[min(e.offset + e.length, last_index)]
        if start == end:  # entity خالی/غیرمنطقی — نادیده گرفته می‌شه
            continue
        spans.append((start, end, wrappers[e.type]))

    if not spans:
        return text

    opens: dict[int, list[tuple[int, str]]] = {}
    closes: dict[int, list[tuple[int, str]]] = {}
    for start, end, wrapper in spans:
        opens.setdefault(start, []).append((end, wrapper))
        closes.setdefault(end, []).append((start, wrapper))

    # در یه موقعیت مشترک: opens با end بزرگ‌تر (بیرونی‌ترین) اول باز بشه؛
    # closes با start بزرگ‌تر (تودرتوترین/تازه‌بازشده) اول بسته بشه.
    for group in opens.values():
        group.sort(key=lambda item: -item[0])
    for group in closes.values():
        group.sort(key=lambda item: -item[0])

    parts: list[str] = []
    for i, ch in enumerate(text):
        for _, wrapper in closes.get(i, ()):
            parts.append(wrapper)
        for _, wrapper in opens.get(i, ()):
            parts.append(wrapper)
        parts.append(ch)
    for _, wrapper in closes.get(len(text), ()):
        parts.append(wrapper)

    return "".join(parts)
