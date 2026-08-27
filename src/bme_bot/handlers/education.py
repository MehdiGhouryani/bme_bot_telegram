# src/bme_bot/handlers/education.py
#
# هندلرهای بخش «آموزش» (منوی آموزش، سوالات متداول، سنسورها و قطعات). محتوای
# متنی/لینک‌ها داخل کد هاردکد نیست؛ از data/faq_content.json و
# data/sensors_components.json خوانده می‌شود.
#
# چیدمان دکمه‌های سنسورها/قطعات هم (لیبل + ترتیب + گروه‌بندی ردیف‌ها) از
# data/sensors_components.json می‌آید (کلیدهای sensors_layout /
# components_layout)؛ یک تابع عمومی (_build_link_keyboard) هر دو کیبورد را از
# روی همین داده می‌سازد — به‌جای دو لیست دکمه‌ی هاردکد و تقریباً تکراری.

import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .. import config
from ..db import feature_usage_repository
from ..keyboards import reply_keyboards
from .menus import make_submenu_handler

_FAQ = None
_SENSORS_COMPONENTS = None


def _load_faq():
    global _FAQ
    if _FAQ is None:
        with open(f"{config.DATA_DIR}/faq_content.json", encoding="utf-8") as f:
            _FAQ = json.load(f)
    return _FAQ


def _load_sensors_components():
    global _SENSORS_COMPONENTS
    if _SENSORS_COMPONENTS is None:
        with open(f"{config.DATA_DIR}/sensors_components.json", encoding="utf-8") as f:
            _SENSORS_COMPONENTS = json.load(f)
    return _SENSORS_COMPONENTS


# به‌جای تابع مستقل، از فکتوری مشترک handlers/menus.py ساخته می‌شود — متن
# پیام و کیبورد عیناً همان قبلی است.
handle_education = make_submenu_handler(
    reply_keyboards.education_menu_keyboard, '  لطفا یکی از گزینه‌ها را انتخاب کنید :'
)


async def handle_back_to_education(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # این تابع عمداً به‌عنوان یک def مستقل نگه داشته شده (نه صرفاً یک نام دوم
    # برای handle_education) — چون تست test_app_routing.py صریحاً
    # education_handler.__name__ == "handle_back_to_education" را بررسی
    # می‌کند.
    await handle_education(update, context)


async def handle_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    faq = _load_faq()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('➡️ برو به صفحه بعد ', callback_data='next_question')]])
    await update.message.reply_text(text=faq["page1"], parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    await feature_usage_repository.log_usage(update.effective_user.id, "faq")


async def show_next_question_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    faq = _load_faq()
    query = update.callback_query
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ برو به صفحه قبل ', callback_data='previous_question')]])
    await query.edit_message_text(text=faq["page2"], parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def show_previous_question_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    faq = _load_faq()
    query = update.callback_query
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton('➡️ برو به صفحه بعد ', callback_data='next_question')]])
    await query.edit_message_text(text=faq["page1"], parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


handle_sensors_components = make_submenu_handler(
    reply_keyboards.sensors_components_menu_keyboard, '  لطفا یکی از گزینه‌ها را انتخاب کنید :'
)


def _build_link_keyboard(url_map: dict, layout: list) -> InlineKeyboardMarkup:
    """یک کیبورد این‌لاین از روی یک نگاشت {کلید: URL} و یک چیدمان [{label, key}]
    می‌سازد (همان الگوی داده‌محور menu_builder.py برای درخت تجهیزات)."""
    rows = []
    for row_spec in layout:
        row = [InlineKeyboardButton(item["label"], url=url_map[item["key"]]) for item in row_spec]
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def handle_sensors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = _load_sensors_components()
    reply_markup = _build_link_keyboard(data["sensors"], data["sensors_layout"])
    await update.message.reply_text(text='یک گزینه را انتخاب کنید : ', reply_markup=reply_markup)
    await feature_usage_repository.log_usage(update.effective_user.id, "sensors")


async def handle_components(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = _load_sensors_components()
    reply_markup = _build_link_keyboard(data["components"], data["components_layout"])
    await update.message.reply_text(text='یک گزینه را انتخاب کنید : ', reply_markup=reply_markup)
    await feature_usage_repository.log_usage(update.effective_user.id, "components")
