# src/bme_bot/handlers/admin.py
#
# پنل ادمین (ترکیبی). جایگزین کامل دو تابع قدیمی
# (handle_user_count/handle_broadcast_post که با تطبیق متن دقیق دو رشته‌ی
# فارسی تایپی فعال می‌شدند و Broadcast هرگز واقعاً کار نمی‌کرد). نقطه‌ی ورود
# واحد: دستور /admin.
#
# جریان‌های چندمرحله‌ای (جستجوی کاربر+بن، Broadcast عکس+کپشن+تایید) با
# ConversationHandler رسمی PTB پیاده شده‌اند، نه پرچم دستی (که بقیه‌ی پروژه
# استفاده می‌کند) — این یک انحراف آگاهانه از سبک غالب پروژه است.
#
# *** نکته‌ی حیاتی برای ثبت در app.py ***
# دو ConversationHandler پایین (user_search_conversation, broadcast_conversation)
# باید در app.py *قبل* از CallbackQueryHandler(callback_handler) عمومی و *قبل*
# از MessageHandler(filters.PHOTO, ocr.handle_photo_message) ثبت شوند — وگرنه
# آن دو handler عمومی (که فیلترشان محدود نیست) زودتر آپدیت را می‌قاپند و
# entry point های این‌جا هرگز اجرا نمی‌شوند.

import asyncio
import logging
from datetime import date, datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Forbidden
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from .. import config
from ..db import (
    admin_actions_repository,
    admins_repository,
    feature_limits_repository,
    feature_usage_repository,
    stt_usage_repository,
    usage_limit_helper,
    users_repository,
)
from ..services import ai_service, ocr_service, stt_service
from ..utils import admin as admin_utils
from ..utils.admin import is_admin, is_main_admin, notify_admins
from ..utils.button_style import DANGER, SUCCESS, styled_button
from ..utils.date_time_entity import date_time_entity

logger = logging.getLogger(__name__)

_NOT_ADMIN_MESSAGE = "شما اجازه‌ی دسترسی به این بخش را ندارید."

# اسم نمایشی فارسی هر فیچر تو پنل، تا متن خام feature_name (مثلاً "stt")
# مستقیم به ادمین نشون داده نشه.
_FEATURE_DISPLAY_NAMES = {
    "ai": "🤖 پرسش از AI",
    "ocr": "📸 تبدیل عکس به متن",
    "stt": "🎙 تبدیل ویس به متن",
    "quiz": "🧠 کوییز از متن",
    "jozve": "🎓 ویس استاد به جزوه",
}
# «quiz_random» عمداً به این دیکشنری اضافه نشده: این دیکشنری هم برای نام
# نمایشی «پربازدیدترین بخش‌ها» و هم — مهم‌تر — برای _format_usage_summary
# پایین‌تر استفاده می‌شود که فرض می‌کند هر کلید اینجا یک سقف روزانه‌ی
# متناظر در _USAGE_TABLE_BY_FEATURE دارد. چون «کوییز تصادفی» عمداً هیچ
# سقفی ندارد، اضافه‌کردنش اینجا (بدون افزودن به _USAGE_TABLE_BY_FEATURE هم)
# باعث AssertionError در تست‌های آن تابع می‌شد. در «پربازدیدترین بخش‌ها»،
# این فیچر مثل «faq»/«sensors»/«components» (که از قبل هم در این دیکشنری
# نیستند) با نام خام «quiz_random» نمایش داده می‌شود.

# اسم نمایشی فارسی هر action خام تو admin_actions (رجوع به همه‌ی
# فراخوانی‌های admin_actions_repository.log_action تو کل کدبیس) — برای
# «📜 آخرین اقدامات ادمین‌ها». اکشن ناشناخته (مثلاً بعد از افزودن یه
# log_action جدید که اینجا فراموش شده) به‌جای کرش، همون رشته‌ی خام رو نشون
# می‌ده (رجوع به _format_actions_log_message).
_ACTION_DISPLAY_NAMES = {
    "ban_user": "⛔️ مسدودسازی کاربر",
    "unban_user": "✅ رفع مسدودی کاربر",
    "broadcast_sent": "📢 ارسال همگانی",
    "limit_changed": "🎚 تغییر محدودیت",
    "toggle_maintenance": "🔧 تغییر وضعیت نگهداری دستگاه",
    "add_maintenance_item": "➕ افزودن آیتم نگهداری",
    "clear_maintenance_item": "🗑 حذف آیتم نگهداری",
    "edit_equipment_field": "✏️ ویرایش محتوای تجهیزات",
    "admin_added": "🛡➕ افزودن ادمین",
    "admin_removed": "🛡➖ حذف ادمین",
    "reset_user_usage": "🔄 ریست محدودیت مصرف کاربر",
}

# --- states (رشته، نه عدد، برای خوانایی لاگ‌ها) ---
SEARCH_AWAITING_QUERY = "admin_search_awaiting_query"
BROADCAST_AWAITING_PHOTO = "admin_broadcast_awaiting_photo"
BROADCAST_AWAITING_CONFIRMATION = "admin_broadcast_awaiting_confirmation"
LIMITS_AWAITING_VALUE = "admin_limits_awaiting_value"
ADMIN_ADD_AWAITING_ID = "admin_add_awaiting_id"

# نرخ ارسال Broadcast: ~۲۵-۳۰ پیام/ثانیه، زیر سقف واقعی تلگرام برای
# جلوگیری از 429.
_BROADCAST_THROTTLE_SECONDS = 1 / 25

# مرجع تسک‌های پس‌زمینه‌ی در حال ارسال Broadcast — صرفاً برای جلوگیری از
# garbage-collect شدن زودهنگام (یک gotcha شناخته‌شده‌ی asyncio.create_task).
_background_broadcast_tasks = set()

# *** نکته‌ی فنی حیاتی ***
# conversation_timeout فقط با یک JobQueue فعال کار می‌کند (تایید‌شده با خواندن
# مستقیم سورس PTB: telegram/ext/_handlers/conversationhandler.py). بدون
# نصب‌شدن extra مربوطه، PTB فقط یک warning لاگ می‌کند و timeout را کاملاً
# نادیده می‌گیرد — به همین دلیل requirements.txt باید
# python-telegram-bot[job-queue] باشد (نه بدون extra).
_CONVERSATION_TIMEOUT_SECONDS = 300


# ============================== منوی اصلی ==============================

def _main_menu_markup(is_main: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="admin_menu:users")],
        [InlineKeyboardButton("📊 آمار", callback_data="admin_menu:stats")],
        [InlineKeyboardButton("🩺 سلامت سیستم", callback_data="admin_menu:health")],
        [InlineKeyboardButton("📢 ارسال همگانی", callback_data="admin_menu:broadcast")],
        [InlineKeyboardButton("🎚 محدودیت‌ها", callback_data="admin_menu:limits")],
    ]
    # تنها دکمه‌ای که فقط برای ادمین اصلی (MAIN_ADMIN_CHAT_ID) رندر می‌شه —
    # بقیه‌ی ادمین‌ها (چه از .env چه اضافه‌شده از همین پنل) به همه‌ی دکمه‌های
    # بالا دسترسی کامل دارن، فقط این یکی نه. رندرنشدن دکمه صرفاً UX است؛
    # محافظت واقعی سمت سرور تو handle_admin_menu_callback/start_add_admin
    # با is_main_admin() انجام می‌شه.
    if is_main:
        rows.append([InlineKeyboardButton("🛡 مدیریت ادمین‌ها", callback_data="admin_menu:admins")])
    return InlineKeyboardMarkup(rows)


def _format_limits_message(limits: list) -> str:
    lines = ["🎚 محدودیت‌های فعلی:\n"]
    for item in limits:
        name = _FEATURE_DISPLAY_NAMES.get(item["feature_name"], item["feature_name"])
        if item["unit"] == "seconds":
            value_str = f"{item['daily_limit'] // 60} دقیقه در روز"
        else:
            value_str = f"{item['daily_limit']} بار در روز"
        lines.append(f"{name}: {value_str} (کول‌داون {item['cooldown_seconds']} ثانیه)")
    lines.append("\nادمین‌ها از همه‌ی این محدودیت‌ها معافن.")
    lines.append("برای ویرایش سقف روزانه‌ی یکی، دکمه‌ش رو بزن:")
    return "\n".join(lines)


def _limits_submenu_markup(limits: list) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            _FEATURE_DISPLAY_NAMES.get(item["feature_name"], item["feature_name"]),
            callback_data=f"admin_limits_edit:{item['feature_name']}",
        )]
        for item in limits
    ]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu:main")])
    return InlineKeyboardMarkup(rows)


def _users_submenu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="admin_users_search_start")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu:main")],
    ])


async def _format_admins_message() -> str:
    static_ids = config.ADMIN_CHAT_ID if isinstance(config.ADMIN_CHAT_ID, (list, tuple)) else []
    dynamic_admins = await admins_repository.list_admins()

    lines = ["🛡 ادمین‌های ربات", ""]
    lines.append("از فایل .env (ثابت — فقط با ویرایش .env و ریستارت بات قابل تغییره):")
    for uid in static_ids:
        tag = " (اصلی)" if is_main_admin(uid) else ""
        lines.append(f"• {uid}{tag}")

    lines.append("")
    if dynamic_admins:
        lines.append("اضافه‌شده از همین پنل:")
        for row in dynamic_admins:
            lines.append(f"• {row['user_id']}")
    else:
        lines.append("هنوز هیچ ادمینی از داخل پنل اضافه نشده.")

    return "\n".join(lines)


def _admins_submenu_markup(dynamic_admins: list) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("➕ افزودن ادمین", callback_data="admin_menu:admins_add")]]
    # فقط ادمین‌های دینامیک (اضافه‌شده از پنل) قابل حذف از اینجان — ردیف‌های
    # ADMIN_CHAT_ID استاتیک همچنان فقط با ویرایش .env قابل تغییرن، دقیقاً
    # مثل قبل، تا این پنل تناقضی با اون منبع ایجاد نکنه.
    for row in dynamic_admins:
        rows.append([InlineKeyboardButton(
            f"➖ حذف {row['user_id']}", callback_data=f"admin_menu:admins_remove:{row['user_id']}",
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu:main")])
    return InlineKeyboardMarkup(rows)


def _back_to_main_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu:main")]])


async def send_daily_summary(context: ContextTypes.DEFAULT_TYPE):
    """خلاصه‌ی روزانه به همه‌ی ادمین‌ها — تعداد تعامل هر فیچر در ۲۴ ساعت اخیر
    + شکست هر ۵ فیچر (نه فقط AI/OCR) بر اساس provider/نوع خطا. زمان‌بندی‌اش
    (run_daily) در app.py است؛ این تابع خودش فقط باید قابل فراخوانی با
    context یک Job باشد — یعنی فقط context.bot لازم دارد، نه هیچ‌چیز مخصوص
    یک آپدیت واقعی (notify_admins هم فقط context.bot می‌خواهد).

    همون حلقه‌ی _format_health_details_message را برای بازه‌ی ۱ روزه تکرار
    می‌کند — عمداً یک منبع مشترک (_FEATURE_DISPLAY_NAMES) دارند تا خلاصه‌ی
    فشرده‌ی push‌شده با نمای کامل داخل پنل ناهماهنگ نشود."""
    feature_counts = await feature_usage_repository.get_feature_counts(days=1)

    lines = ["📅 خلاصه‌ی روزانه‌ی ربات (۲۴ ساعت اخیر)", "", "📈 تعامل بر اساس فیچر"]
    if feature_counts:
        for feature, count in feature_counts.items():
            lines.append(f"• {feature}: {count}")
    else:
        lines.append("(هیچ تعاملی ثبت نشد)")
    lines.append("")

    for feature, display in _FEATURE_DISPLAY_NAMES.items():
        breakdown = await feature_usage_repository.get_detail_breakdown(feature, days=1)
        failure = await feature_usage_repository.get_detail_breakdown(f"{feature}_failure", days=1)
        lines += _format_breakdown_section(f"{display} — کدام لایه پاسخ داد", breakdown)
        if failure:
            lines += _format_breakdown_section(f"{display} — شکست‌ها", failure)
        lines.append("")

    await notify_admins(context, "\n".join(lines).rstrip())


async def open_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin — نقطه‌ی ورود واحد پنل ادمین (جایگزین دو دکمه‌ی تایپی قدیمی)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text(_NOT_ADMIN_MESSAGE)
        return
    await update.message.reply_text("پنل مدیریت ربات:", reply_markup=_main_menu_markup(is_main_admin(user.id)))


def _stats_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 آخرین اقدامات ادمین‌ها", callback_data="admin_menu:actions_log")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu:main")],
    ])


def _actions_log_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به آمار", callback_data="admin_menu:stats")],
    ])


async def _format_actions_log_message() -> tuple[str, list]:
    """آخرین اقدامات ادمین‌ها — admin_actions_repository.get_recent_actions
    از قبل نوشته و تست شده بود (docstring خودش می‌گفت «برای بخش آمار/بازبینی
    پنل ادمین») ولی به هیچ‌جای پنل وصل نبود؛ یعنی هر بن/آنبن/Broadcast/تغییر
    محدودیت/افزودن-حذف ادمین ثبت می‌شد ولی دیدنش فقط از راه دسترسی مستقیم
    به دیتابیس ممکن بود.

    هر timestamp با یک date_time entity نشون داده می‌شه (دقیقاً مثل
    _format_profile برای تاریخ عضویت/آخرین فعالیت) تا کلاینت تلگرام با
    تایم‌زون محلی خودش نمایشش بده، نه رشته‌ی خام UTC."""
    actions = await admin_actions_repository.get_recent_actions(limit=20)

    text = "📜 آخرین اقدامات ادمین‌ها (۲۰ مورد اخیر)\n\n"
    entities = []

    if not actions:
        return text + "(هنوز هیچ اقدامی ثبت نشده)", entities

    for row in actions:
        raw_ts = row["timestamp"]
        ts_dt = _parse_stored_utc(raw_ts) if raw_ts else None
        ts_text = raw_ts if raw_ts else "نامشخص"

        if ts_dt:
            entities.append(date_time_entity(text, ts_text, ts_dt))
        text += f"🕐 {ts_text}\n"

        label = _ACTION_DISPLAY_NAMES.get(row["action"], row["action"])
        target_suffix = f" — {row['target']}" if row["target"] else ""
        text += f"👤 {row['admin_id']} • {label}{target_suffix}\n\n"

    return text.rstrip(), entities


async def _format_stats_message() -> str:
    user_stats = await users_repository.get_user_stats()
    feature_counts = await feature_usage_repository.get_feature_counts(days=7)

    lines = [
        "📊 آمار کلی کاربران",
        f"کل کاربران: {user_stats['total']}",
        f"جدید (۲۴ ساعت اخیر): {user_stats['new_today']}",
        f"جدید (۷ روز اخیر): {user_stats['new_week']}",
        f"جدید (۳۰ روز اخیر): {user_stats['new_month']}",
        f"فعال (۷ روز اخیر): {user_stats['active_7d']}",
        f"فعال (۳۰ روز اخیر): {user_stats['active_30d']}",
        f"مسدودشده: {user_stats['banned']}",
        "",
        "📈 پربازدیدترین بخش‌ها (۷ روز اخیر)",
    ]

    if feature_counts:
        for feature, count in feature_counts.items():
            lines.append(f"• {feature}: {count}")
    else:
        lines.append("(هنوز داده‌ای ثبت نشده)")

    return "\n".join(lines)


def _format_breakdown_section(title: str, breakdown: dict) -> list:
    """یک بخش «برچسب: تعداد (درصد)» می‌سازد — بین هر ۴ ترکیب فیچر/بازه در
    _format_health_message مشترک است تا فرمت‌شان یکی بماند."""
    lines = [title]
    total = sum(breakdown.values())
    if not breakdown:
        lines.append("(هنوز داده‌ای ثبت نشده)")
        return lines
    for detail, count in breakdown.items():
        percent = round(100 * count / total) if total else 0
        lines.append(f"• {detail}: {count} ({percent}%)")
    return lines


def _health_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 جزئیات کامل (۳۰ روز + شکست‌ها)", callback_data="admin_menu:health_details")],
        [InlineKeyboardButton("🩺 تست سرویس‌ها الان", callback_data="admin_menu:health_test")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu:main")],
    ])


def _health_details_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به سلامت سیستم", callback_data="admin_menu:health")],
    ])


async def _format_health_message() -> str:
    """نمای پیش‌فرض «سلامت سیستم» — سهم هر provider/مدل از هر ۵ فیچر
    (نه فقط AI/OCR) در ۷ روز اخیر. عمداً کوتاه نگه داشته شده (بدون بازه‌ی
    ۳۰ روزه، بدون بخش شکست‌ها — پشت دکمه‌ی «جزئیات کامل»ان) تا این پیام
    همیشه یه‌نگاهی و قابل‌اسکن بمونه.

    این دقیقاً همون فرمتیه (تفکیک provider/مدل، نه فقط تعداد کل) که اگه
    برای STT/کوییز/جزوه‌ساز هم از قبل فعال بود، خرابی کامل مدل
    gemini-2.5-flash رو (سهم ۰٪ از لایه‌ی اول، ۱۰۰٪ افتادن رو fallback)
    همون لحظه لو می‌داد — نه فقط از راه خوندن دستی لاگ production."""
    lines = ["🩺 سلامت سیستم (۷ روز اخیر)", ""]
    for feature, display in _FEATURE_DISPLAY_NAMES.items():
        breakdown = await feature_usage_repository.get_detail_breakdown(feature, days=7)
        lines += _format_breakdown_section(display, breakdown)
        lines.append("")
    return "\n".join(lines).rstrip()


async def _format_health_details_message() -> str:
    """جزئیات کامل: هر ۵ فیچر، هم ۷ هم ۳۰ روز، هم موفق (به تفکیک
    provider/مدل) هم ناموفق (به تفکیک نوع خطا — feature_failure، رجوع به
    error_reporting._log_persistent_failure). بخش شکست‌ها فقط وقتی نشون
    داده می‌شه که واقعاً شکستی ثبت شده — برای این‌که حالت خوب (بدون خطا)
    این پیام رو با «بدون داده» های تکراری شلوغ نکنه."""
    lines = ["📈 جزئیات کامل سلامت سیستم", ""]
    _PERSIAN_DAYS = {7: "۷", 30: "۳۰"}  # همون قرارداد بقیه‌ی پیام‌های این فایل (اعداد فارسی برای بازه‌های ثابت)
    for feature, display in _FEATURE_DISPLAY_NAMES.items():
        for days in (7, 30):
            days_fa = _PERSIAN_DAYS[days]
            success = await feature_usage_repository.get_detail_breakdown(feature, days=days)
            lines += _format_breakdown_section(f"{display} — {days_fa} روز اخیر", success)
            failure = await feature_usage_repository.get_detail_breakdown(f"{feature}_failure", days=days)
            if failure:
                lines.append("")
                lines += _format_breakdown_section(f"{display} — شکست‌ها ({days_fa} روز اخیر)", failure)
            lines.append("")
    return "\n".join(lines).rstrip()


def _service_test_result_lines(results: list[tuple[str, bool | None, str]]) -> list[str]:
    lines = []
    for name, ok, message in results:
        icon = "⚪️" if ok is None else ("✅" if ok else "❌")
        lines.append(f"{icon} {name}: {message}")
    return lines


async def _format_service_test_message() -> str:
    """نتیجه‌ی زنده‌ی تست هر مدل/provider AI/OCR/STT، *مستقل از هم* (نه
    فقط تا اولین موفقیت مثل مسیر واقعی درخواست کاربر) — دکمه‌ی «🩺 تست
    سرویس‌ها الان» تو «🩺 سلامت سیستم». دقیقاً همون چیزیه که اگه از قبل
    بود، خرابی مدل gemini-2.5-flash (۴۰۴ روی *هر* درخواست، بی‌سروصدا
    افتادن رو fallback) رو با یه تست دستی همون لحظه لو می‌داد، نه فقط از
    راه خوندن دستی لاگ production چند روز بعد.

    ⚪️ یعنی provider اصلاً پیکربندی نشده (نه یه شکست واقعی) — کلید API‌اش
    تنظیم نیست، پس جدا از ✅/❌ نگه داشته شده تا با یه خطای واقعی قاطی
    نشه."""
    lines = ["🩺 نتیجه‌ی تست سرویس‌ها (همین الان)", "", "🤖 AI:"]
    lines += _service_test_result_lines(await ai_service.test_all_models())
    lines += ["", "📸 OCR:"]
    lines += _service_test_result_lines(await ocr_service.test_all_providers())
    lines += ["", "🎙 STT:"]
    lines += _service_test_result_lines(await stt_service.test_all_providers())
    return "\n".join(lines)


async def handle_admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دیسپچر بخش‌های *بدون حالت* منوی ادمین (آمار، زیرمنوی کاربران، بازگشت).
    از callback_handler عمومی (app.py) صدا زده می‌شود — برخلاف جستجو/Broadcast
    که ConversationHandler جدای خودشان را دارند و هرگز به این تابع نمی‌رسند
    (چون آن دو زودتر، پیش از callback_handler، ثبت شده‌اند)."""
    query = update.callback_query
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer(_NOT_ADMIN_MESSAGE, show_alert=True)
        return

    await query.answer()
    data = query.data

    if data == "admin_menu:stats":
        await query.edit_message_text(await _format_stats_message(), reply_markup=_stats_markup())
    elif data == "admin_menu:actions_log":
        text, entities = await _format_actions_log_message()
        await query.edit_message_text(text, entities=entities, reply_markup=_actions_log_markup())
    elif data == "admin_menu:health":
        await query.edit_message_text(await _format_health_message(), reply_markup=_health_markup())
    elif data == "admin_menu:health_details":
        await query.edit_message_text(await _format_health_details_message(), reply_markup=_health_details_markup())
    elif data == "admin_menu:health_test":
        # این تست تا ~۲۰ درخواست واقعی شبکه می‌زنه (هر مدل/provider جدا)،
        # ممکنه چند ثانیه طول بکشه — یه پیام میانی می‌ذاریم تا ادمین فکر
        # نکنه بات فریز کرده.
        await query.edit_message_text("⏳ در حال تست همه‌ی مدل‌ها و provider ها... (چند ثانیه طول می‌کشه)")
        await query.edit_message_text(await _format_service_test_message(), reply_markup=_health_details_markup())
    elif data == "admin_menu:users":
        await query.edit_message_text("مدیریت کاربران:", reply_markup=_users_submenu_markup())
    elif data == "admin_menu:main":
        await query.edit_message_text("پنل مدیریت ربات:", reply_markup=_main_menu_markup(is_main_admin(user.id)))
    elif data == "admin_menu:limits":
        limits = await feature_limits_repository.get_all_limits()
        await query.edit_message_text(_format_limits_message(limits), reply_markup=_limits_submenu_markup(limits))
    elif data == "admin_menu:admins":
        # دکمه فقط برای ادمین اصلی رندر می‌شه، ولی callback_data خودش
        # مخفی نیست — دفاع در عمق: سمت سرور هم صریح چک می‌کنیم، نه فقط
        # رندرنکردن دکمه.
        if not is_main_admin(user.id):
            await query.message.reply_text(_NOT_ADMIN_MESSAGE)
            return
        dynamic_admins = await admins_repository.list_admins()
        await query.edit_message_text(
            await _format_admins_message(), reply_markup=_admins_submenu_markup(dynamic_admins),
        )
    elif data.startswith("admin_menu:admins_remove:"):
        if not is_main_admin(user.id):
            await query.message.reply_text(_NOT_ADMIN_MESSAGE)
            return
        target_id = int(data.rsplit(":", 1)[-1])
        removed = await admin_utils.remove_dynamic_admin(target_id)
        if removed:
            await admin_actions_repository.log_action(user.id, "admin_removed", target=str(target_id))
            try:
                await context.bot.send_message(chat_id=target_id, text="دسترسی ادمین شما به ربات لغو شد.")
            except Exception as e:
                logger.debug("notify removed admin failed: %s", e)
        dynamic_admins = await admins_repository.list_admins()
        await query.edit_message_text(
            await _format_admins_message(), reply_markup=_admins_submenu_markup(dynamic_admins),
        )


# ============================== جستجو + بن/آنبن کاربر ==============================

def _parse_stored_utc(value: str):
    """رشته‌ی ذخیره‌شده در users_repository.py (فرمت %Y-%m-%d %H:%M:%S،
    همیشه UTC — رجوع به users_repository._utc_now_str) را به یک datetime
    واقعاً timezone-aware تبدیل می‌کند. روی هر فرمت غیرمنتظره (داده‌ی خیلی
    قدیمی یا دستکاری‌شده) None برمی‌گرداند تا فراخواننده به متن ساده
    برگردد، نه این‌که کل پیام پروفایل با خطا شکست بخورد."""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


_USAGE_TABLE_BY_FEATURE = {"ai": "ai_usage", "ocr": "ocr_usage", "quiz": "quiz_usage", "jozve": "jozve_usage"}


async def _format_usage_summary(user_id: int) -> str:
    """خلاصه‌ی مصرف *امروز* این کاربر از هر ۵ فیچر، در برابر سقف روزانه‌ی
    فعلی — برای پشتیبانی («چرا نمی‌تونم ازش استفاده کنم؟ / سقفم پر شده؟»)
    خیلی به‌درد می‌خوره؛ قبلاً پروفایل جستجوی ادمین فقط شناسه/یوزرنیم/
    وضعیت عضویت/بن رو نشون می‌داد، هیچ‌جا مصرف واقعی این کاربر دیده
    نمی‌شد. count-محور (ai/ocr/quiz/jozve، هر ۴ با یک مخزن مشترک) و
    ثانیه-محور (stt، مخزن کاملاً جدا — رجوع به کامنت بالای
    stt_usage_repository.py) جدا خونده می‌شن.

    last_date را با امروز مقایسه می‌کنیم چون request_count خودش خودکار
    صفر نمی‌شه — فقط وقتی check_limit/check_stt_limit واقعاً صدا زده بشه
    (دفعه‌ی بعدی که کاربر از اون فیچر استفاده کنه) ریست می‌شه؛ همون منطقی
    که خودِ آن توابع برای «روز عوض شده یا نه» دارند، اینجا هم باید تکرار
    بشه، وگرنه عدد دیروز به‌اشتباه «امروز» نشون داده می‌شه."""
    today = date.today().isoformat()
    lines = ["📊 مصرف امروز:"]

    for feature, table in _USAGE_TABLE_BY_FEATURE.items():
        display = _FEATURE_DISPLAY_NAMES[feature]
        daily_limit, _, _ = await feature_limits_repository.get_limit(feature)
        row = await usage_limit_helper.get_usage_for_user(table, user_id)
        count = row["count"] if row and row["last_date"] == today else 0
        lines.append(f"{display}: {count} / {daily_limit}")

    stt_limit_seconds, _, _ = await feature_limits_repository.get_limit("stt")
    stt_row = await stt_usage_repository.get_usage_for_user(user_id)
    stt_seconds = stt_row["seconds"] if stt_row and stt_row["last_date"] == today else 0
    lines.append(
        f"{_FEATURE_DISPLAY_NAMES['stt']}: {stt_seconds // 60} از {stt_limit_seconds // 60} دقیقه"
    )

    return "\n".join(lines)


async def _format_profile(profile: dict) -> tuple[str, list]:
    """متن پروفایل + لیست MessageEntity های date_time برای تاریخ عضویت و
    آخرین فعالیت — کلاینت تلگرام خودش این‌ها را با تایم‌زون محلی کاربر
    نمایش می‌دهد، به‌جای رشته‌ی خام UTC. اگر مقدار خام قابل‌پارس نبود
    (یا اصلاً وجود نداشت)، همان‌طور که قبلاً بود به‌صورت متن ساده می‌ماند —
    entity برایش ساخته نمی‌شود، نه این‌که پیام را بشکند.

    async شد تا خلاصه‌ی مصرف (_format_usage_summary، چند کوئری دیتابیس)
    هم به همین متن اضافه بشه — بعد از ساخته‌شدن entityهای تاریخ، پس آفست
    اون‌ها با این افزودن به‌هم نمی‌خوره."""
    status = "🚫 مسدود" if profile["is_banned"] else "✅ فعال"
    username = f"@{profile['username']}" if profile["username"] else "—"

    header = f"👤 کاربر {profile['user_id']}\n"
    username_line = f"نام‌کاربری: {username}\n"
    status_line = f"وضعیت: {status}\n"
    joined_prefix = "تاریخ عضویت: "
    last_seen_prefix = "\nآخرین فعالیت: "

    entities = []

    joined_raw = profile["joined_at"]
    joined_dt = _parse_stored_utc(joined_raw) if joined_raw else None
    joined_text = joined_raw if joined_raw else "نامشخص"
    preceding = header + username_line + status_line + joined_prefix
    if joined_dt:
        entities.append(date_time_entity(preceding, joined_text, joined_dt))

    last_seen_raw = profile["last_seen_at"]
    last_seen_dt = _parse_stored_utc(last_seen_raw) if last_seen_raw else None
    last_seen_text = last_seen_raw if last_seen_raw else "نامشخص"
    preceding_for_last_seen = preceding + joined_text + last_seen_prefix
    if last_seen_dt:
        entities.append(date_time_entity(preceding_for_last_seen, last_seen_text, last_seen_dt))

    usage_text = await _format_usage_summary(profile["user_id"])
    text = (
        f"{header}{username_line}{status_line}{joined_prefix}{joined_text}"
        f"{last_seen_prefix}{last_seen_text}\n\n{usage_text}"
    )
    return text, entities


def _profile_markup(profile: dict) -> InlineKeyboardMarkup:
    if profile["is_banned"]:
        ban_button = styled_button(
            "✅ رفع مسدودی", SUCCESS, callback_data=f"admin_toggle_ban:{profile['user_id']}:unban"
        )
    else:
        ban_button = styled_button(
            "🚫 مسدود کردن", DANGER, callback_data=f"admin_toggle_ban:{profile['user_id']}:ban"
        )
    return InlineKeyboardMarkup([
        [ban_button],
        [InlineKeyboardButton(
            "🔄 ریست محدودیت‌های امروز", callback_data=f"admin_reset_usage:{profile['user_id']}",
        )],
        [InlineKeyboardButton("🏁 پایان جستجو", callback_data="admin_search_end")],
    ])


async def start_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer(_NOT_ADMIN_MESSAGE, show_alert=True)
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        "شناسه‌ی عددی (user_id) یا نام‌کاربری فرد موردنظر را بفرستید.\n"
        "برای پایان، /cancel را بفرستید."
    )
    return SEARCH_AWAITING_QUERY


async def receive_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = await users_repository.search_user(update.message.text)

    if not results:
        await update.message.reply_text("کاربری با این مشخصات پیدا نشد. دوباره امتحان کنید یا /cancel بزنید.")
        return SEARCH_AWAITING_QUERY

    if len(results) > 1:
        lines = "\n".join(f"• {u['user_id']} — @{u['username'] or '—'}" for u in results)
        await update.message.reply_text(
            f"{len(results)} کاربر پیدا شد؛ لطفاً با شناسه‌ی دقیق‌تری جستجو کنید:\n{lines}"
        )
        return SEARCH_AWAITING_QUERY

    profile = results[0]
    text, entities = await _format_profile(profile)
    await update.message.reply_text(text, entities=entities, reply_markup=_profile_markup(profile))
    return SEARCH_AWAITING_QUERY


async def toggle_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_user = update.effective_user
    if not admin_user or not is_admin(admin_user.id):
        await query.answer(_NOT_ADMIN_MESSAGE, show_alert=True)
        return SEARCH_AWAITING_QUERY

    _, target_user_id_str, new_state = query.data.split(":")
    target_user_id = int(target_user_id_str)
    banned = new_state == "ban"

    # دروازه‌ی سراسری (global_gate.py) بن را حتی روی /admin هم اعمال می‌کند —
    # یعنی اگر یک ادمین دیگری را بن کند، آن ادمین کاملاً از خودِ ربات (از جمله
    # /admin برای رفع‌بن خودش) قفل می‌شود، بدون هیچ راه بازگشتی جز دسترسی
    # مستقیم به دیتابیس. برای جلوگیری از این قفل‌شدگی، بن‌کردن یک ادمین دیگر
    # اینجا صراحتاً رد می‌شود.
    if banned and is_admin(target_user_id):
        await query.answer("نمی‌توانید یک ادمین دیگر را مسدود کنید.", show_alert=True)
        return SEARCH_AWAITING_QUERY

    await users_repository.set_banned(target_user_id, banned)
    await admin_actions_repository.log_action(
        admin_user.id, "ban_user" if banned else "unban_user", target=str(target_user_id)
    )
    await query.answer("✅ انجام شد.")

    refreshed = await users_repository.search_user(str(target_user_id))
    if refreshed:
        text, entities = await _format_profile(refreshed[0])
        await query.edit_message_text(text, entities=entities, reply_markup=_profile_markup(refreshed[0]))
    return SEARCH_AWAITING_QUERY


async def reset_user_usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «🔄 ریست محدودیت‌های امروز» تو پروفایل جستجوی ادمین — شمارنده‌ی
    امروز هر ۵ فیچر رو برای همین یک کاربر صفر می‌کنه (بدون دست‌زدن به سقف
    سراسری همه‌ی کاربران، که از قبل با «🎚 محدودیت‌ها» قابل‌تغییره). برای
    پشتیبانی («سقفم پر شده، می‌شه یه درخواست دیگه امروز بدید؟») است."""
    query = update.callback_query
    admin_user = update.effective_user
    if not admin_user or not is_admin(admin_user.id):
        await query.answer(_NOT_ADMIN_MESSAGE, show_alert=True)
        return SEARCH_AWAITING_QUERY

    target_user_id = int(query.data.split(":")[1])
    await usage_limit_helper.reset_all_usage_for_user(target_user_id)
    await stt_usage_repository.reset_usage_for_user(target_user_id)
    await admin_actions_repository.log_action(admin_user.id, "reset_user_usage", target=str(target_user_id))
    await query.answer("✅ محدودیت‌های امروز این کاربر ریست شد.")

    refreshed = await users_repository.search_user(str(target_user_id))
    if refreshed:
        text, entities = await _format_profile(refreshed[0])
        await query.edit_message_text(text, entities=entities, reply_markup=_profile_markup(refreshed[0]))
    return SEARCH_AWAITING_QUERY


async def end_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("پایان جستجو.")
    else:
        await update.effective_message.reply_text("پایان جستجو.")
    return ConversationHandler.END


async def remind_text_needed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اگر ادمین حین جستجو چیزی غیر از متن بفرستد (عکس، استیکر، ...)،
    ConversationHandler آن را ادعا نمی‌کند و بدون این هندلر آپدیت بی‌صدا به
    هندلر بعدی (مثلاً OCR) سُر می‌خورد — بدون هیچ بازخوردی به ادمین. مثل
    remind_photo_needed در Broadcast، یک یادآوری صریح نشان داده می‌شود."""
    await update.message.reply_text("لطفاً یک شناسه‌ی عددی یا نام‌کاربری متنی بفرستید یا /cancel را بزنید.")
    return SEARCH_AWAITING_QUERY


async def handle_search_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی جستجوی کاربر بدون فعالیت به conversation_timeout برسد.

    آخرین updateای که PTB اینجا پاس می‌دهد می‌تواند پیام متنی *یا* callback
    query باشد (رفتار داخلی ConversationHandler._trigger_timeout) — به
    همین دلیل عمداً از reply_text/edit_message_text استفاده نشده (که فقط
    روی یکی از این دو نوع update کار می‌کند)، بلکه از effective_chat +
    context.bot.send_message که روی هر دو یکسان کار می‌کند."""
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ زمان جستجو تمام شد. برای شروع دوباره /admin را بزنید.",
        )


user_search_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_user_search, pattern="^admin_users_search_start$")],
    states={
        SEARCH_AWAITING_QUERY: [
            CallbackQueryHandler(toggle_ban, pattern=r"^admin_toggle_ban:\d+:(ban|unban)$"),
            CallbackQueryHandler(reset_user_usage, pattern=r"^admin_reset_usage:\d+$"),
            CallbackQueryHandler(end_search, pattern="^admin_search_end$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_search_query),
            MessageHandler(~filters.COMMAND, remind_text_needed),
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, handle_search_timeout)],
    },
    fallbacks=[CommandHandler("cancel", end_search)],
    conversation_timeout=_CONVERSATION_TIMEOUT_SECONDS,
    name="admin_user_search",
)


# ============================== Broadcast ==============================

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer(_NOT_ADMIN_MESSAGE, show_alert=True)
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        "یک عکس همراه با کپشن دلخواه بفرستید — همین پیام عیناً به همه‌ی "
        "کاربران غیرمسدود فرستاده می‌شود.\nبرای لغو، /cancel را بفرستید."
    )
    return BROADCAST_AWAITING_PHOTO


async def receive_broadcast_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    caption = update.message.caption or ""
    context.user_data["broadcast_photo_file_id"] = photo.file_id
    context.user_data["broadcast_caption"] = caption

    preview_caption = caption if caption else "(بدون کپشن)"
    await update.message.reply_photo(
        photo=photo.file_id,
        caption=f"پیش‌نمایش پیامی که به همه فرستاده می‌شود:\n\n{preview_caption}",
        reply_markup=InlineKeyboardMarkup([
            [styled_button("✅ ارسال به همه", SUCCESS, callback_data="admin_broadcast_confirm")],
            # لغو، رنگ نمی‌گیره: بازگشت/انصراف اکشن مخرب نیست که DANGER بخواد،
            # و "موفقیت" هم نیست که SUCCESS بخواد — خنثی می‌ماند.
            [InlineKeyboardButton("❌ لغو", callback_data="admin_broadcast_cancel")],
        ]),
    )
    return BROADCAST_AWAITING_CONFIRMATION


async def remind_photo_needed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لطفاً یک عکس بفرستید (نه متن) یا /cancel را بزنید.")
    return BROADCAST_AWAITING_PHOTO


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("broadcast_photo_file_id", None)
    context.user_data.pop("broadcast_caption", None)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_caption(caption="❌ لغو شد.", reply_markup=None)
    else:
        await update.effective_message.reply_text("❌ لغو شد.")
    return ConversationHandler.END


async def _broadcast_worker(context: ContextTypes.DEFAULT_TYPE, admin_id: int, photo_file_id: str, caption: str):
    """تسک پس‌زمینه‌ی ارسال واقعی — عمداً از confirm_and_send_broadcast جدا
    شده تا ادمین منتظر اتمام کل ارسال (که برای چند صد کاربر می‌تواند چند
    دقیقه طول بکشد) نماند.

    اگر users_repository.get_all_active_chat_ids() یا
    admin_actions_repository.log_action (که عمداً خطا را قورت نمی‌دهد؛ طبق
    خودِ admin_actions_repository.py) با خطای غیرمنتظره مواجه شوند، هر سه
    بخش (دریافت مقصدها، لاگ اقدام، ارسال خلاصه) مستقل محافظت شده‌اند تا
    ادمین *همیشه* یک پیام نهایی دریافت کند — نه این‌که کل تابع پیش از
    رسیدن به پیام خلاصه‌ی نهایی متوقف شود و ادمین هیچ‌وقت نفهمد Broadcast
    چه سرنوشتی پیدا کرد.
    """
    success_count = 0
    failed_count = 0
    unexpected_failure = False

    try:
        chat_ids = await users_repository.get_all_active_chat_ids()
    except Exception:
        logger.exception("دریافت لیست مقصدهای Broadcast شکست خورد (ادمین %s).", admin_id)
        chat_ids = []
        unexpected_failure = True

    for chat_id in chat_ids:
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=photo_file_id, caption=caption or None)
            success_count += 1
        except Forbidden:
            # کاربر ربات را بلاک کرده — این باید per-recipient گرفته شود تا
            # یک کاربر کل Broadcast را متوقف نکند.
            failed_count += 1
        except Exception:
            logger.exception("ارسال Broadcast به %s شکست خورد.", chat_id)
            failed_count += 1
        await asyncio.sleep(_BROADCAST_THROTTLE_SECONDS)

    try:
        await admin_actions_repository.log_action(
            admin_id, "broadcast_sent",
            target=f"{success_count} موفق / {failed_count} ناموفق از {len(chat_ids)}",
        )
    except Exception:
        logger.exception("ثبت لاگ اقدام Broadcast شکست خورد (ادمین %s).", admin_id)

    summary = f"📢 ارسال همگانی تمام شد.\n✅ موفق: {success_count}\n❌ ناموفق: {failed_count}"
    if unexpected_failure:
        summary += "\n\n⚠️ در دریافت لیست کاربران خطایی رخ داد؛ ممکن است ارسال ناقص بوده باشد. جزئیات در لاگ سرور."

    try:
        await context.bot.send_message(chat_id=admin_id, text=summary)
    except Exception:
        logger.exception("ارسال خلاصه‌ی Broadcast به ادمین %s شکست خورد.", admin_id)


async def confirm_and_send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    admin_user = update.effective_user
    await query.answer("ارسال آغاز شد...")
    await query.edit_message_caption(caption="⏳ در حال ارسال به همه‌ی کاربران... (خلاصه‌ی نهایی جداگانه می‌آید)", reply_markup=None)

    photo_file_id = context.user_data.pop("broadcast_photo_file_id", None)
    caption = context.user_data.pop("broadcast_caption", "")

    task = asyncio.create_task(_broadcast_worker(context, admin_user.id, photo_file_id, caption))
    _background_broadcast_tasks.add(task)
    task.add_done_callback(_background_broadcast_tasks.discard)

    return ConversationHandler.END


async def handle_broadcast_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مشابه handle_search_timeout — علاوه‌بر اطلاع‌رسانی، عکس/کپشن نیم‌کاره‌ی
    احتمالی را هم از user_data پاک می‌کند تا اگر ادمین بعداً یک Broadcast
    تازه شروع کرد، داده‌ی قدیمی باقی نماند."""
    context.user_data.pop("broadcast_photo_file_id", None)
    context.user_data.pop("broadcast_caption", None)
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ زمان ارسال همگانی تمام شد و لغو شد. برای شروع دوباره /admin را بزنید.",
        )


broadcast_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_broadcast, pattern="^admin_menu:broadcast$")],
    states={
        BROADCAST_AWAITING_PHOTO: [
            MessageHandler(filters.PHOTO, receive_broadcast_photo),
            MessageHandler(filters.TEXT & ~filters.COMMAND, remind_photo_needed),
        ],
        BROADCAST_AWAITING_CONFIRMATION: [
            CallbackQueryHandler(confirm_and_send_broadcast, pattern="^admin_broadcast_confirm$"),
            CallbackQueryHandler(cancel_broadcast, pattern="^admin_broadcast_cancel$"),
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, handle_broadcast_timeout)],
    },
    fallbacks=[CommandHandler("cancel", cancel_broadcast)],
    conversation_timeout=_CONVERSATION_TIMEOUT_SECONDS,
    name="admin_broadcast",
)


# ============================== محدودیت‌های قابل‌تنظیم ==============================
#
# ادمین یه فیچر رو از زیرمنوی «🎚 محدودیت‌ها» انتخاب می‌کنه، بات سقف فعلی
# رو نشون می‌ده و منتظر یه عدد جدید می‌مونه. برای STT عدد به *دقیقه* از
# ادمین گرفته می‌شه (نه ثانیه‌ی خام ذخیره‌شده تو دیتابیس) چون خواناتره؛
# قبل از ذخیره در ۶۰ ضرب می‌شه.

async def start_limit_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer(_NOT_ADMIN_MESSAGE, show_alert=True)
        return ConversationHandler.END

    await query.answer()
    feature_name = query.data.split(":", 1)[1]
    context.user_data["editing_limit_feature"] = feature_name

    daily_limit, _cooldown_seconds, unit = await feature_limits_repository.get_limit(feature_name)
    display_name = _FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)

    if unit == "seconds":
        prompt = (
            f"سقف روزانه‌ی جدید «{display_name}» رو به دقیقه بفرست "
            f"(فعلی: {daily_limit // 60} دقیقه):"
        )
    else:
        prompt = f"سقف روزانه‌ی جدید «{display_name}» رو بفرست (فعلی: {daily_limit} بار):"

    await query.edit_message_text(prompt + "\n\nبرای لغو، /cancel را بفرستید.")
    return LIMITS_AWAITING_VALUE


async def receive_limit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    feature_name = context.user_data.get("editing_limit_feature")
    text = (update.message.text or "").strip()

    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("لطفاً یه عدد صحیح مثبت بفرست (یا /cancel برای لغو):")
        return LIMITS_AWAITING_VALUE

    new_value = int(text)
    _, _cooldown_seconds, unit = await feature_limits_repository.get_limit(feature_name)
    stored_value = new_value * 60 if unit == "seconds" else new_value

    await feature_limits_repository.set_daily_limit(feature_name, stored_value)
    try:
        await admin_actions_repository.log_action(
            update.effective_user.id, "limit_changed", target=f"{feature_name}={stored_value}",
        )
    except Exception:
        logger.exception("ثبت لاگ اقدام تغییر محدودیت شکست خورد.")

    context.user_data.pop("editing_limit_feature", None)
    display_name = _FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
    unit_label = "دقیقه در روز" if unit == "seconds" else "بار در روز"
    await update.message.reply_text(f"✅ سقف «{display_name}» به {new_value} {unit_label} تغییر کرد.")
    return ConversationHandler.END


async def cancel_limit_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("editing_limit_feature", None)
    await update.message.reply_text("ویرایش محدودیت لغو شد.")
    return ConversationHandler.END


async def handle_limits_edit_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("editing_limit_feature", None)
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ زمان ویرایش محدودیت تمام شد و لغو شد. برای شروع دوباره /admin را بزنید.",
        )


limits_edit_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_limit_edit, pattern=r"^admin_limits_edit:(ai|ocr|stt|quiz|jozve)$"),
    ],
    states={
        LIMITS_AWAITING_VALUE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_limit_value),
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, handle_limits_edit_timeout)],
    },
    fallbacks=[CommandHandler("cancel", cancel_limit_edit)],
    conversation_timeout=_CONVERSATION_TIMEOUT_SECONDS,
    name="admin_limits_edit",
)


# ============================== مدیریت ادمین‌ها (فقط ادمین اصلی) ==============================
#
# افزودن ادمین از داخل بات، مکمل فهرست استاتیک .env — فقط ادمین اصلی
# (config.MAIN_ADMIN_CHAT_ID) دسترسی داره؛ تنها بخش پنل که این‌طوریه، بقیه‌ی
# همه‌چیز (کاربران، آمار، سلامت، Broadcast، محدودیت‌ها) برای هر ادمینی —
# چه از .env چه اضافه‌شده از همین‌جا — یکسان در دسترسه. جزئیات کامل تصمیم
# (چرا cache حافظه‌ای به‌جای async‌کردن is_admin) در utils/admin.py.

async def start_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user = update.effective_user
    if not user or not is_main_admin(user.id):
        await query.answer(_NOT_ADMIN_MESSAGE, show_alert=True)
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        "شناسه‌ی عددی (user_id) کاربری که می‌خواید ادمین بشه رو بفرستید.\n"
        "برای گرفتن شناسه‌ی عددی یه نفر، کافیه بگید یه پیام از @userinfobot "
        "براش بفرسته یا پیامش رو به یه ربات شناسه‌گیر فوروارد کنه.\n"
        "برای لغو، /cancel را بفرستید."
    )
    return ADMIN_ADD_AWAITING_ID


async def receive_new_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text(
            "این یه شناسه‌ی عددی معتبر نیست. لطفاً فقط عدد شناسه‌ی تلگرام رو بفرستید، "
            "یا /cancel برای لغو."
        )
        return ADMIN_ADD_AWAITING_ID

    new_admin_id = int(text)
    admin_user = update.effective_user

    if is_admin(new_admin_id):
        await update.message.reply_text("این کاربر همین الان هم ادمینه — کاری انجام نشد.")
        return ConversationHandler.END

    await admin_utils.add_dynamic_admin(new_admin_id, added_by=admin_user.id)
    await admin_actions_repository.log_action(admin_user.id, "admin_added", target=str(new_admin_id))

    try:
        await context.bot.send_message(
            chat_id=new_admin_id,
            text="🛡 شما به‌عنوان ادمین ربات اضافه شدید. برای دیدن پنل مدیریت، دستور /admin را بزنید.",
        )
    except Exception as e:
        # کاربر جدید ممکنه هیچ‌وقت با بات چت خصوصی شروع نکرده باشه —
        # تلگرام اجازه نمی‌ده بات پیام‌رسان اول باشه؛ افزودن خودش قبلاً با
        # موفقیت انجام و ذخیره شده، فقط این اطلاع‌رسانی جانبیه.
        logger.debug("notify new admin failed: %s", e)

    await update.message.reply_text(f"✅ کاربر {new_admin_id} به‌عنوان ادمین اضافه شد.")
    return ConversationHandler.END


async def remind_admin_id_needed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("لطفاً یک شناسه‌ی عددی بفرستید یا /cancel را بزنید.")
    return ADMIN_ADD_AWAITING_ID


async def cancel_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
    await update.effective_message.reply_text("لغو شد.")
    return ConversationHandler.END


async def handle_add_admin_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ زمان تمام شد و لغو شد. برای شروع دوباره /admin را بزنید.",
        )


admin_add_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_admin, pattern="^admin_menu:admins_add$")],
    states={
        ADMIN_ADD_AWAITING_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_admin_id),
            MessageHandler(~filters.COMMAND, remind_admin_id_needed),
        ],
        ConversationHandler.TIMEOUT: [TypeHandler(Update, handle_add_admin_timeout)],
    },
    fallbacks=[CommandHandler("cancel", cancel_add_admin)],
    conversation_timeout=_CONVERSATION_TIMEOUT_SECONDS,
    name="admin_add",
)
