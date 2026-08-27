# src/bme_bot/handlers/menus.py
#
# فکتوری مشترک برای هندلرهای «نمایش یک زیرمنوی Reply ساده». پیش از این، سه
# هندلر در دو فایل مختلف (education.handle_education،
# education.handle_sensors_components، ocr.handle_tools_menu) دقیقاً همین
# قالب را تکرار می‌کردند:
#     async def handle_X(update, context):
#         reply_markup = reply_keyboards.X_menu_keyboard()
#         await update.message.reply_text("متن ثابت", reply_markup=reply_markup)
# همان فلسفه‌ی «داده به‌جای کد تکراری» که در equipment_tree.py + menu_builder.py
# برای درخت تجهیزات جواب داده، اینجا برای زیرمنوهای Reply هم به‌کار رفته.
#
# نکته‌ی مهم: handle_faq در این فکتوری قرار نمی‌گیرد — کیبورد آن این‌لاین با
# pagination است، نه یک ساخت ساده‌ی Reply. handle_back_to_main (start.py)
# هم عمداً دست‌نخورده ماند.

from telegram import Update
from telegram.ext import ContextTypes


def make_submenu_handler(keyboard_fn, prompt_text: str):
    """یک هندلر آماده‌ی ثبت در _BUTTON_HANDLERS می‌سازد: با کلیک روی دکمه،
    prompt_text را به همراه کیبوردِ حاصل از keyboard_fn() (یکی از
    reply_keyboards.*_menu_keyboard، بدون آرگومان) پاسخ می‌دهد."""
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(prompt_text, reply_markup=keyboard_fn())

    return handler
