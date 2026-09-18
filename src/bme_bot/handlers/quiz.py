# src/bme_bot/handlers/quiz.py
# هندلر ابزار «کوییز از متن یا فایل». ابتدا تعداد سوال دلخواه (۲ تا ۱۰) با
# دکمه‌ی inline پرسیده می‌شه، بعد متن درسی *یا* یه فایل Word(.docx)/متنی(.txt)
# قبول می‌شه → ai_service.ask() با پرامپت پارامتری‌شده‌ی quiz_prompt.json →
# JSON چندسوالی → هرکدوم به شکل quiz poll بومی تلگرام (send_poll type=QUIZ)
# فرستاده می‌شه.
#
# فاز Q1:
# - تعداد سوال قبلاً هاردکد ۵ بود؛ الان با دکمه انتخاب می‌شه و در پرامپت
#   جایگزین __QUESTION_COUNT__ می‌شه (نه str.format — چون خودِ پرامپت مثال
#   JSON با آکولاد واقعی داره که format() را می‌شکست).
# - استخراج متن از فایل با docx2txt (pure-Python، بدون وابستگی C، برخلاف
#   python-docx که به lxml نیاز داره — چون فقط متن خام برای پرامپت AI لازمه،
#   نه دستکاری ساختاریافته‌ی خودِ Word).
# - سقف طول متن استخراج‌شده (۴۰۹۶ کاراکتر): قبل از این فیچر، کوییز-از-متن
#   عملاً به همین عدد محدود بود چون ورودی از یه پیام متنی تلگرام می‌اومد
#   (سقف خودِ تلگرام برای طول پیام). با آپلود فایل این سقف طبیعی از بین
#   می‌ره؛ چون سقف توکن روزانه‌ی fallback مشترک Groq بین همه‌ی فیچرهای
#   AI-محور محدوده (رجوع به README.md)، همون سقف قبلی رو عمداً نگه داشتیم
#   تا این فیچر ریسک بودجه‌ی مشترک روزانه رو بیشتر از چیزی که کوییز-از-متن
#   از قبل داشت نکنه — نه یه عدد دلخواه جدید.

from __future__ import annotations

import io
import json
import logging
import zipfile

import docx2txt
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Poll, Update
from telegram.ext import ContextTypes

from .. import config
from ..db import feature_usage_repository, quiz_usage_repository
from ..services import ai_service
from ..utils import admin as admin_utils
from ..utils import error_reporting, messages, quiz_archive

logger = logging.getLogger(__name__)

_PROMPT: str | None = None

_QUESTION_COUNT_PLACEHOLDER = "__QUESTION_COUNT__"
_QUESTION_COUNT = 5  # fallback اگر به هر دلیلی شمارش user_data گم شده باشه
_MIN_QUESTION_COUNT = 2
_MAX_QUESTION_COUNT = 10

_MAX_QUESTION_LENGTH = 250  # سقف واقعی تلگرام ۲۵۵ است
_MAX_OPTION_LENGTH = 95  # سقف واقعی تلگرام ۱۰۰ است
_MAX_EXPLANATION_LENGTH = 195  # سقف واقعی تلگرام ۲۰۰ است

# سقف مستند Telegram Bot API برای دانلود فایل توسط بات (همون سقف پلتفرمی که
# jozve.py هم استفاده می‌کنه، نه یه تصمیم محصولی جدا).
_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
# دلیل عدد در بالای فایل مستند شده — عمداً همون سقف ضمنی قبلی کوییز-از-متن.
_MAX_UPLOADED_TEXT_LENGTH = 4096

_SUPPORTED_EXTENSIONS = frozenset({"docx", "txt"})

_QUESTION_COUNT_PROMPT = "چند تا سوال می‌خوای؟ 🔢"
_PROMPT_FOR_TEXT_MESSAGE = (
    "لطفاً متن درسی‌ای که می‌خواید ازش کوییز بسازم رو بفرستید،\n"
    "یا یه فایل Word (.docx) یا متنی (.txt) آپلود کنید 🧠"
)
_PROCESSING_MESSAGE = "⏳ در حال طراحی کوییز..."
_GENERIC_ERROR_MESSAGE = "متاسفانه در ساخت کوییز مشکلی پیش اومد. لطفاً دوباره امتحان کنید."
_EMPTY_RESPONSE_MESSAGE = "نتونستم از این متن کوییز بسازم. یه متن دیگه امتحان کنید."
_INVALID_COUNT_MESSAGE = "این گزینه دیگه معتبر نیست. لطفاً دوباره روی «🎓 کوییز» بزنید."
_FILE_TOO_LARGE_MESSAGE = "حجم این فایل بیش‌ازحد بزرگه (سقف تلگرام ۲۰ مگابایته)."
_UNSUPPORTED_FORMAT_MESSAGE = "این فرمت فایل پشتیبانی نمی‌شه. لطفاً یه فایل Word (.docx) یا متنی (.txt) بفرستید."
_LEGACY_DOC_MESSAGE = (
    "فرمت قدیمی Word (.doc) پشتیبانی نمی‌شه. لطفاً فایل رو با فرمت .docx ذخیره کنید و دوباره بفرستید."
)
_EMPTY_ARCHIVE_MESSAGE = (
    "هنوز هیچ کوییزی در آرشیو نیست 🙂 یه کوییز از «🧠 کوییز از متن» بساز تا آرشیو پر بشه!"
)
_EXTRACTION_FAILED_MESSAGE = (
    "این فایل قابل‌خوندن نبود. مطمئن شو فایل Word معتبره (خراب یا رمزگذاری‌شده نباشه) و دوباره امتحان کن."
)


class QuizGenerationError(Exception):
    """پاسخ AI قابل‌پارس یا معتبر نبود."""


class UnsupportedDocumentFormat(Exception):
    """پسوند فایل جزو _SUPPORTED_EXTENSIONS نیست."""


class DocumentExtractionFailed(Exception):
    """فایل .docx معتبر (zip سالم با ساختار Word) نبود."""


def _load_prompt() -> str:
    global _PROMPT
    if _PROMPT is None:
        with open(f"{config.DATA_DIR}/quiz_prompt.json", encoding="utf-8") as f:
            _PROMPT = json.load(f)["system"]
    return _PROMPT


def _format_prompt(question_count: int) -> str:
    return _load_prompt().replace(_QUESTION_COUNT_PLACEHOLDER, str(question_count))


def _question_count_markup() -> InlineKeyboardMarkup:
    numbers = range(_MIN_QUESTION_COUNT, _MAX_QUESTION_COUNT + 1)
    row1 = [InlineKeyboardButton(str(n), callback_data=f"quiz_count:{n}") for n in numbers if n <= 6]
    row2 = [InlineKeyboardButton(str(n), callback_data=f"quiz_count:{n}") for n in numbers if n > 6]
    return InlineKeyboardMarkup([row1, row2])


def _get_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _extract_text_from_bytes(file_bytes: bytes, extension: str) -> str:
    if extension == "txt":
        return file_bytes.decode("utf-8", errors="replace")
    if extension == "docx":
        try:
            return docx2txt.process(io.BytesIO(file_bytes))
        except (zipfile.BadZipFile, KeyError) as e:
            raise DocumentExtractionFailed(str(e)) from e
    raise UnsupportedDocumentFormat(extension)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _parse_and_validate_quiz(raw_text: str) -> list[dict]:
    try:
        data = json.loads(_strip_code_fence(raw_text))
    except (ValueError, TypeError) as e:
        raise QuizGenerationError(f"JSON پارس نشد: {e}")

    if not isinstance(data, list) or not data:
        raise QuizGenerationError("خروجی یه آرایه‌ی غیرخالی نبود")

    validated = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise QuizGenerationError(f"سوال {i}: آبجکت نیست")
        question = str(item.get("question", "")).strip()
        options = item.get("options")
        correct_index = item.get("correct_index")
        explanation = str(item.get("explanation", "")).strip()

        if not question:
            raise QuizGenerationError(f"سوال {i}: question خالیه")
        if not isinstance(options, list) or len(options) != 4:
            raise QuizGenerationError(f"سوال {i}: دقیقاً باید ۴ گزینه باشه")
        if not all(str(opt).strip() for opt in options):
            raise QuizGenerationError(f"سوال {i}: یه گزینه خالیه")
        if not isinstance(correct_index, int) or not (0 <= correct_index <= 3):
            raise QuizGenerationError(f"سوال {i}: correct_index نامعتبره")

        validated.append({
            "question": question[:_MAX_QUESTION_LENGTH],
            "options": [str(opt).strip()[:_MAX_OPTION_LENGTH] for opt in options],
            "correct_index": correct_index,
            "explanation": explanation[:_MAX_EXPLANATION_LENGTH],
        })

    return validated


async def handle_quiz_tool_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(_QUESTION_COUNT_PROMPT, reply_markup=_question_count_markup())


async def handle_random_quiz_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی «🎲 کوییز تصادفی». برخلاف handle_quiz_tool_selected هیچ AI
    فراخوانی نمی‌کند و هیچ سقف مصرف روزانه ندارد — فقط یک ردیف تصادفی از
    آرشیوِ از‌قبل‌تولیدشده (quiz_archive.jsonl) می‌خواند، پس هزینه‌ی
    بودجه‌ی مشترک AI صفر است و برای ادمین/کاربر عادی فرقی نمی‌کند."""
    question = await quiz_archive.get_random_question()
    if question is None:
        await update.message.reply_text(_EMPTY_ARCHIVE_MESSAGE)
        return

    user_id = update.effective_user.id
    await feature_usage_repository.log_usage(user_id, "quiz_random")
    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=question["question"],
        options=question["options"],
        type=Poll.QUIZ,
        correct_option_id=question["correct_index"],
        explanation=question["explanation"] or None,
        is_anonymous=True,
    )


async def handle_quiz_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """callback_data: quiz_count:{n}. بعد از انتخاب تعداد، پرچم awaiting_quiz_text
    فعال می‌شه — از همین‌جا به بعد جریان قبلی (متن یا فایل) شروع می‌شه."""
    query = update.callback_query
    try:
        count = int(data.split(":", 1)[1])
    except (IndexError, ValueError):
        await query.answer(_INVALID_COUNT_MESSAGE, show_alert=True)
        return
    if not (_MIN_QUESTION_COUNT <= count <= _MAX_QUESTION_COUNT):
        await query.answer(_INVALID_COUNT_MESSAGE, show_alert=True)
        return

    context.user_data["quiz_question_count"] = count
    context.user_data["awaiting_quiz_text"] = True
    await query.answer()
    await query.edit_message_text(_PROMPT_FOR_TEXT_MESSAGE)


async def _generate_and_send_quiz(
    update: Update, context: ContextTypes.DEFAULT_TYPE, study_text: str, question_count: int,
):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not config.GEMINI_API_KEY:
        await update.message.reply_text(messages.AI_UNAVAILABLE)
        # قبلاً هیچ گزارشی به ادمین نمی‌رفت این‌جا — شاخه‌ی
        # except ai_service.AIServiceUnavailable پایین‌تر تنها جای این کار
        # بود ولی چون این چک همیشه زودتر برمی‌گرده، هیچ‌وقت بهش نمی‌رسید.
        await error_reporting.report_service_issue(
            context, "GEMINI_API_KEY تنظیم نشده است.",
            context_label="quiz", failure_feature="quiz", user_id=user_id,
        )
        return

    if not study_text:
        await update.message.reply_text(_EMPTY_RESPONSE_MESSAGE)
        return

    is_admin_user = admin_utils.is_admin(user_id)
    if not is_admin_user:
        can_process, limit_message = await quiz_usage_repository.check_quiz_limit(user_id)
        if not can_process:
            await update.message.reply_text(f"⚠️ {limit_message}")
            return
        await quiz_usage_repository.record_attempt(user_id)
    processing_message = await update.message.reply_text(_PROCESSING_MESSAGE)

    try:
        raw_text, model_used = await ai_service.ask(study_text, _format_prompt(question_count))
        questions = _parse_and_validate_quiz(raw_text)
    except ai_service.AIResponseEmpty as e:
        # برخلاف QuizGenerationError پایین‌تر (که AI واقعاً پاسخ داده ولی
        # JSON نامعتبر بوده)، این حالت یعنی یه درخواست AI واقعی زده و
        # توکن مصرف شده، فقط محتوا خالی/بلاک‌شده بوده — همون منطقی که
        # jozve.py برای AIResponseEmpty در مرحله‌ی ساختاردهی به کار می‌بره
        # (رجوع به تست‌های متناظر در هردو فایل).
        if not is_admin_user:
            await quiz_usage_repository.increment_quiz_usage(user_id)
        await processing_message.edit_text(
            "متاسفانه به دلیل محدودیت‌های ایمنی، امکان ساخت کوییز از این متن نیست."
            if e.blocked else _EMPTY_RESPONSE_MESSAGE
        )
        return
    except ai_service.AIServiceUnavailable as e:
        await processing_message.edit_text(messages.AI_UNAVAILABLE)
        await error_reporting.report_service_issue(
            context, str(e), context_label="quiz", failure_feature="quiz", user_id=user_id,
        )
        return
    except QuizGenerationError as e:
        logger.warning("Quiz JSON validation failed for user %s: %s", user_id, e)
        await processing_message.edit_text(_EMPTY_RESPONSE_MESSAGE)
        await error_reporting.report_service_issue(
            context, f"quiz JSON validation failed: {e}",
            context_label="quiz", failure_feature="quiz", user_id=user_id,
        )
        return
    except Exception as e:
        logger.exception("Quiz unexpected error for user %s", user_id)
        await processing_message.edit_text(_GENERIC_ERROR_MESSAGE)
        await error_reporting.report_error(
            context, e, context_label="quiz", failure_feature="quiz", user_id=user_id,
        )
        return

    if not is_admin_user:
        await quiz_usage_repository.increment_quiz_usage(user_id)
    await feature_usage_repository.log_usage(user_id, "quiz", detail=model_used)
    await quiz_archive.archive_quiz(user_id, questions, model_used)

    await processing_message.delete()
    for q in questions:
        await context.bot.send_poll(
            chat_id=chat_id,
            question=q["question"],
            options=q["options"],
            type=Poll.QUIZ,
            correct_option_id=q["correct_index"],
            explanation=q["explanation"] or None,
            is_anonymous=True,
        )


async def handle_quiz_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط وقتی awaiting_quiz_text فعال است عمل می‌کند."""
    if not context.user_data.get("awaiting_quiz_text"):
        return

    context.user_data.pop("awaiting_quiz_text", None)
    question_count = context.user_data.pop("quiz_question_count", _QUESTION_COUNT)
    study_text = (update.message.text or "").strip()

    await _generate_and_send_quiz(update, context, study_text, question_count)


async def handle_quiz_document_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط وقتی awaiting_quiz_text فعال است عمل می‌کند (همون پرچم مسیر متنی —
    یه فایل هم پاسخ معتبری به همون پرامپت «متن یا فایل بفرست» است)."""
    if not context.user_data.get("awaiting_quiz_text"):
        return
    context.user_data.pop("awaiting_quiz_text", None)
    question_count = context.user_data.pop("quiz_question_count", _QUESTION_COUNT)

    document = update.message.document
    if document is None:
        return

    extension = _get_extension(document.file_name)
    if extension not in _SUPPORTED_EXTENSIONS:
        message = _LEGACY_DOC_MESSAGE if extension == "doc" else _UNSUPPORTED_FORMAT_MESSAGE
        await update.message.reply_text(message)
        return

    if document.file_size and document.file_size > _MAX_DOWNLOAD_BYTES:
        await update.message.reply_text(_FILE_TOO_LARGE_MESSAGE)
        return

    telegram_file = await context.bot.get_file(document.file_id)
    file_bytes = bytes(await telegram_file.download_as_bytearray())

    if len(file_bytes) > _MAX_DOWNLOAD_BYTES:
        await update.message.reply_text(_FILE_TOO_LARGE_MESSAGE)
        return

    try:
        extracted_text = _extract_text_from_bytes(file_bytes, extension)
    except DocumentExtractionFailed as e:
        logger.warning("Quiz document extraction failed for user %s: %s", update.effective_user.id, e)
        await update.message.reply_text(_EXTRACTION_FAILED_MESSAGE)
        return

    extracted_text = extracted_text.strip()
    if len(extracted_text) > _MAX_UPLOADED_TEXT_LENGTH:
        await update.message.reply_text(
            f"این فایل خیلی طولانیه ({len(extracted_text)} کاراکتر؛ سقف {_MAX_UPLOADED_TEXT_LENGTH} کاراکتره). "
            "لطفاً یه بخش کوتاه‌تر رو امتحان کنید."
        )
        return

    await _generate_and_send_quiz(update, context, extracted_text, question_count)
