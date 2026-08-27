# src/bme_bot/app.py
# ساخت Application، ثبت handlerها، دو دیسپچر سطح‌بالا.

import datetime
import logging

import pytz
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from . import config, logging_setup
from .db.app_connection import setup_users_database
from .db.maintenance_repository import setup_tables as setup_maintenance_tables
from .handlers import (
    admin,
    ai_assistant,
    education,
    equipment_admin_edit,
    equipment_callbacks,
    global_gate,
    jozve,
    maintenance_admin_edit,
    maintenance_callbacks,
    membership,
    ocr,
    quiz,
    start,
    stt,
    suggestion,
)
from .keyboards import menu_builder, reply_keyboards
from .utils import error_reporting, telegram_error_handler

logger = logging.getLogger(__name__)

_SOFT_ERROR_MSG = "سرویس موقتاً در دسترس نیست. لطفاً کمی بعد دوباره تلاش کنید."

_CONNECT_TIMEOUT = 15.0
_READ_TIMEOUT = 40.0
_WRITE_TIMEOUT = 40.0
_POOL_TIMEOUT = 10.0


async def _clear_user_state(context: ContextTypes.DEFAULT_TYPE):
    for key in (
        "awaiting_request", "awaiting_ai_question", "awaiting_ocr_image",
        "awaiting_stt_voice", "awaiting_quiz_text", "awaiting_jozve_audio",
    ):
        context.user_data.pop(key, None)


_BUTTON_HANDLERS = {
    reply_keyboards.EDUCATION_TEXT: education.handle_education,
    reply_keyboards.FAQ_TEXT: education.handle_faq,
    reply_keyboards.SUGGESTION_TEXT: suggestion.handle_suggestion,
    reply_keyboards.AI_ASK_TEXT: ai_assistant.handle_ai_ask,
    reply_keyboards.TOOLS_TEXT: ocr.handle_tools_menu,
    reply_keyboards.OCR_TOOL_TEXT: ocr.handle_ocr_tool_selected,
    reply_keyboards.STT_TOOL_TEXT: stt.handle_stt_tool_selected,
    reply_keyboards.QUIZ_TOOL_TEXT: quiz.handle_quiz_tool_selected,
    reply_keyboards.JOZVE_TOOL_TEXT: jozve.handle_jozve_tool_selected,
    reply_keyboards.MEDICAL_EQUIPMENT_TEXT: equipment_callbacks.show_main_menu,
    reply_keyboards.SENSORS_COMPONENTS_TEXT: education.handle_sensors_components,
    reply_keyboards.SENSORS_TEXT: education.handle_sensors,
    reply_keyboards.COMPONENTS_TEXT: education.handle_components,
    reply_keyboards.BACK_TO_MAIN_TEXT: start.handle_back_to_main,
    reply_keyboards.BACK_TO_EDUCATION_TEXT: education.handle_back_to_education,
}


@membership.membership_required
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    handler = _BUTTON_HANDLERS.get(text)

    if handler:
        await _clear_user_state(context)
        await handler(update, context)
    elif context.user_data.get("awaiting_request"):
        await suggestion.handle_suggestion_message(update, context)
    elif context.user_data.get("awaiting_ai_question"):
        await ai_assistant.handle_ai_confirmation(update, context)
    elif context.user_data.get("awaiting_quiz_text"):
        await quiz.handle_quiz_text_message(update, context)


@membership.membership_required
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    try:
        await query.answer()
    except Exception:
        pass

    if await equipment_callbacks.route(update, context, data):
        return

    if data.startswith("maint_view_"):
        await maintenance_callbacks.route(update, context, data)
        return

    if data.startswith("quiz_count:"):
        await quiz.handle_quiz_count_callback(update, context, data)
        return

    if data.startswith("ai_"):
        await ai_assistant.handle_ai_callback(update, context, data)
        return

    if data.startswith("admin_menu:"):
        await admin.handle_admin_menu_callback(update, context)
        return

    if data == "back_to_main":
        reply_markup = menu_builder.get_main_menu_markup()
        try:
            await query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception as e:
            logger.warning("back_to_main edit failed: %s", e)
    elif data == "check_membership":
        await membership.check_membership(update, context)
    elif data == "next_question":
        await education.show_next_question_page(update, context)
    elif data == "previous_question":
        await education.show_previous_question_page(update, context)
    else:
        try:
            await query.answer("این بخش هنوز آماده نشده است.", show_alert=True)
        except Exception:
            pass


async def _describe_update(update: object) -> str:
    if not isinstance(update, Update):
        return f"update:{type(update).__name__}"
    if update.callback_query:
        return f"callback_data={update.callback_query.data!r}"
    if update.effective_message and update.effective_message.text:
        return f"text={update.effective_message.text!r}"
    return "نامشخص"


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شبکه ایمنی سراسری: گزارش به ادمین + پیام نرم به کاربر (بدون جزئیات فنی)."""
    error = context.error
    label = await _describe_update(update)
    await error_reporting.report_error(context, error, context_label=label)

    try:
        if not isinstance(update, Update):
            return
        if update.callback_query:
            try:
                await update.callback_query.answer(_SOFT_ERROR_MSG, show_alert=True)
            except Exception:
                if update.effective_chat:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id, text=_SOFT_ERROR_MSG,
                    )
        elif update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=_SOFT_ERROR_MSG,
            )
    except Exception as e:
        logger.warning("user soft-notice failed: %s", e)


async def _post_init(application: Application):
    await setup_users_database()
    await setup_maintenance_tables()
    application.job_queue.run_daily(
        admin.send_daily_summary,
        time=datetime.time(hour=9, minute=0, tzinfo=pytz.timezone("Asia/Tehran")),
        name="daily_summary",
    )


def main():
    logging_setup.configure_logging()

    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "متغیر محیطی Token تنظیم نشده است. فایل .env.example را ببینید."
        )
    if not config.ADMIN_CHAT_ID:
        logger.warning(
            "ADMIN_CHAT_ID خالی است — گزارش ادمین و دستورات /admin کار نخواهند کرد."
        )

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(_CONNECT_TIMEOUT)
        .read_timeout(_READ_TIMEOUT)
        .write_timeout(_WRITE_TIMEOUT)
        .pool_timeout(_POOL_TIMEOUT)
        .post_init(_post_init)
        .build()
    )

    # TelegramAdminErrorHandler به یک Bot instance نیاز دارد (نه context)،
    # پس بلافاصله بعد از ساخته‌شدن Application ست می‌شود.
    telegram_error_handler.set_bot(app.bot)

    app.add_handler(
        TypeHandler(Update, global_gate.enforce_ban_and_track_activity), group=-1,
    )

    app.add_handler(CommandHandler("ask", ai_assistant.ask_command))
    app.add_handler(CommandHandler("ai", ai_assistant.ai_command))
    app.add_handler(CommandHandler("start", start.start, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("admin", admin.open_admin_panel, filters=filters.ChatType.PRIVATE))

    app.add_handler(admin.user_search_conversation)
    app.add_handler(admin.broadcast_conversation)
    app.add_handler(admin.limits_edit_conversation)
    app.add_handler(equipment_admin_edit.equipment_edit_conversation)
    app.add_handler(maintenance_admin_edit.maintenance_admin_conversation)

    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, button_click)
    )
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO, ocr.handle_photo_message)
    )
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.Document.ALL, quiz.handle_quiz_document_message)
    )
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.VOICE, stt.handle_voice_message)
    )
    # group=1: بعد از handler های بالا (group پیش‌فرض ۰) پردازش می‌شود. لازم
    # چون stt.handle_voice_message هم دقیقاً همین filters.VOICE را می‌گیرد —
    # در یک group، تلگرام فقط اولین handler منطبق را اجرا می‌کند، نه همه را؛
    # پس این handler باید در یک group جدا باشد تا وقتی awaiting_stt_voice
    # ست نیست (یعنی پیام واقعاً برای جزوه‌سازی است)، نوبتش هم برسد.
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.VOICE | filters.AUDIO),
            jozve.handle_jozve_audio_message,
        ),
        group=1,
    )
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_error_handler(global_error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()