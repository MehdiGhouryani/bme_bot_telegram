# tests/test_quiz_handlers.py
#
# تست هندلر کوییز: مدیریت پرچم awaiting_quiz_text، پارس/اعتبارسنجی JSON
# خروجی AI، و ارسال quiz poll بومی تلگرام. ساختار عیناً از
# test_ocr_handlers.py/test_stt_handlers.py الگو گرفته شده.

import io
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram import Poll

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import quiz_usage_repository  # noqa: E402
from bme_bot.handlers import quiz  # noqa: E402
from bme_bot.services import ai_service  # noqa: E402
from bme_bot.utils import admin as admin_utils  # noqa: E402
from bme_bot.utils import error_reporting, messages, quiz_archive  # noqa: E402

# رجوع به دو تست پایین فایل (test_archive_quiz_writes_valid_jsonl_end_to_end و
# test_archive_quiz_appends_across_multiple_calls_without_overwriting):
# فیکسچر autouse زیر quiz_archive.archive_quiz رو برای *همه‌ی* تست‌های این
# فایل mock می‌کنه، پس اون دو تست (که عمداً می‌خوان تابع واقعی رو صدا
# بزنن، نه mock رو) باید یه رفرنس مستقل و دست‌نخورده از تابع واقعی داشته
# باشن — همین‌جا، قبل از اینکه هر fixture ای اجرا بشه (یعنی موقع
# import شدن خودِ این فایل) گرفته می‌شه.
_real_archive_quiz = quiz_archive.archive_quiz


def _make_minimal_docx(paragraphs: list[str]) -> bytes:
    """یه .docx حداقلی و معتبر می‌سازه، فقط با zipfile استاندارد (بدون
    وابستگی به python-docx که جزو requirements.txt پروژه نیست) — دقیقاً
    همون ساختار XML که docx2txt.xml2text انتظار داره (w:p/w:r/w:t)."""
    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()

_VALID_QUESTION = {
    "question": "فرکانس نایکوئیست چیه؟",
    "options": ["نصف فرکانس نمونه‌برداری", "دو برابر فرکانس سیگنال", "برابر فرکانس سیگنال", "هیچکدام"],
    "correct_index": 1,
    "explanation": "باید حداقل دو برابر بالاترین فرکانس سیگنال باشه.",
}


def _valid_quiz_json(count=5):
    return json.dumps([_VALID_QUESTION] * count, ensure_ascii=False)


@pytest.fixture(autouse=True)
def _configured_and_allowed_by_default(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: False)
    monkeypatch.setattr(quiz_usage_repository, "check_quiz_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(quiz_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(quiz_usage_repository, "increment_quiz_usage", AsyncMock())
    # پیش‌فرض mock می‌شه تا هیچ تست عادی‌ای فایل آرشیو واقعی رو ننویسه —
    # تست‌های خودِ آرشیو (پایین‌تر) دوباره monkeypatch می‌کنن تا این
    # پیش‌فرض رو override کنن.
    monkeypatch.setattr(quiz_archive, "archive_quiz", AsyncMock())


def _make_update_with_text(text="فرکانس نایکوئیست باید دو برابر بالاترین فرکانس سیگنال باشه."):
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    update = SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=4242),
        effective_chat=SimpleNamespace(id=777),
    )
    return update, message


def _make_context(user_data=None):
    return SimpleNamespace(user_data=user_data if user_data is not None else {}, bot=SimpleNamespace(send_poll=AsyncMock()))


# ------------------------------- پارس/اعتبارسنجی JSON -------------------------------

def test_parse_valid_json_returns_five_questions():
    questions = quiz._parse_and_validate_quiz(_valid_quiz_json())
    assert len(questions) == 5
    assert questions[0]["correct_index"] == 1


def test_parse_strips_markdown_code_fence():
    fenced = "```json\n" + _valid_quiz_json(count=1) + "\n```"
    questions = quiz._parse_and_validate_quiz(fenced)
    assert len(questions) == 1


def test_parse_rejects_invalid_json():
    with pytest.raises(quiz.QuizGenerationError):
        quiz._parse_and_validate_quiz("این اصلا JSON نیست")


def test_parse_rejects_wrong_option_count():
    bad = dict(_VALID_QUESTION)
    bad["options"] = ["فقط دو گزینه", "همین"]
    with pytest.raises(quiz.QuizGenerationError):
        quiz._parse_and_validate_quiz(json.dumps([bad], ensure_ascii=False))


def test_parse_rejects_out_of_range_correct_index():
    bad = dict(_VALID_QUESTION)
    bad["correct_index"] = 7
    with pytest.raises(quiz.QuizGenerationError):
        quiz._parse_and_validate_quiz(json.dumps([bad], ensure_ascii=False))


def test_parse_truncates_overlong_fields_instead_of_rejecting():
    long_q = dict(_VALID_QUESTION)
    long_q["question"] = "س" * 500
    long_q["explanation"] = "ت" * 500
    questions = quiz._parse_and_validate_quiz(json.dumps([long_q], ensure_ascii=False))
    assert len(questions[0]["question"]) <= quiz._MAX_QUESTION_LENGTH
    assert len(questions[0]["explanation"]) <= quiz._MAX_EXPLANATION_LENGTH


# ------------------------------- جریان هندلر -------------------------------

@pytest.mark.asyncio
async def test_text_ignored_when_not_awaiting_quiz_text():
    update, message = _make_update_with_text()
    context = _make_context(user_data={})

    await quiz.handle_quiz_text_message(update, context)

    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_tool_selected_shows_question_count_picker():
    """فاز Q1: قبل از پرسیدن متن/فایل، اول تعداد سوال دلخواه پرسیده می‌شه."""
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={})

    await quiz.handle_quiz_tool_selected(update, context)

    assert "awaiting_quiz_text" not in context.user_data  # هنوز نه — اول باید تعداد انتخاب بشه
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.await_args
    assert args[0] == quiz._QUESTION_COUNT_PROMPT
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_successful_quiz_sends_five_native_polls(monkeypatch):
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=(_valid_quiz_json(), "gemini/gemini-2.5-flash")))

    await quiz.handle_quiz_text_message(update, context)

    assert context.bot.send_poll.await_count == 5
    quiz_usage_repository.increment_quiz_usage.assert_awaited_once_with(4242)
    processing_msg.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_poll_uses_correct_option_id_and_quiz_type(monkeypatch):
    from telegram import Poll

    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(
        ai_service, "ask", AsyncMock(return_value=(_valid_quiz_json(count=1), "groq/openai/gpt-oss-120b"))
    )

    await quiz.handle_quiz_text_message(update, context)

    _, kwargs = context.bot.send_poll.call_args
    assert kwargs["type"] == Poll.QUIZ
    assert kwargs["correct_option_id"] == 1
    assert kwargs["chat_id"] == 777


@pytest.mark.asyncio
async def test_empty_text_message_rejected_without_calling_ai(monkeypatch):
    update, message = _make_update_with_text(text="   ")
    context = _make_context(user_data={"awaiting_quiz_text": True})
    ask_mock = AsyncMock(side_effect=AssertionError("ask نباید صدا زده بشه"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await quiz.handle_quiz_text_message(update, context)

    ask_mock.assert_not_called()
    message.reply_text.assert_awaited_once_with(quiz._EMPTY_RESPONSE_MESSAGE)


@pytest.mark.asyncio
async def test_rejected_when_daily_limit_reached(monkeypatch):
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    monkeypatch.setattr(
        quiz_usage_repository, "check_quiz_limit",
        AsyncMock(return_value=(False, "شما از تمام 5 کوییز روزانه‌ی خود استفاده کرده‌اید.")),
    )
    ask_mock = AsyncMock(side_effect=AssertionError("ask نباید صدا زده بشه"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await quiz.handle_quiz_text_message(update, context)

    ask_mock.assert_not_called()
    message.reply_text.assert_awaited_once_with("⚠️ شما از تمام 5 کوییز روزانه‌ی خود استفاده کرده‌اید.")


@pytest.mark.asyncio
async def test_ai_service_unavailable_reports_to_admin(monkeypatch):
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIServiceUnavailable("no key")))
    report_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_mock)

    await quiz.handle_quiz_text_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(messages.AI_UNAVAILABLE)
    report_mock.assert_awaited_once()
    _, kwargs = report_mock.call_args
    assert kwargs["failure_feature"] == "quiz"
    context.bot.send_poll.assert_not_called()


@pytest.mark.asyncio
async def test_malformed_ai_json_reports_to_admin_and_shows_friendly_message(monkeypatch):
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("این JSON معتبر نیست", "gemini/gemini-2.5-flash")))
    report_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_mock)

    await quiz.handle_quiz_text_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(quiz._EMPTY_RESPONSE_MESSAGE)
    report_mock.assert_awaited_once()
    context.bot.send_poll.assert_not_called()
    quiz_usage_repository.increment_quiz_usage.assert_not_called()


@pytest.mark.asyncio
async def test_ai_response_empty_blocked_shows_safety_message(monkeypatch):
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIResponseEmpty(blocked=True)))

    await quiz.handle_quiz_text_message(update, context)

    processing_msg.edit_text.assert_awaited_once()
    assert "ایمنی" in processing_msg.edit_text.await_args.args[0]
    # درخواست AI واقعی زده شده (توکن مصرف شده)، پس برخلاف JSON نامعتبر،
    # سهمیه باید مصرف بشه — هم‌راستا با jozve.py برای همین exception.
    quiz_usage_repository.increment_quiz_usage.assert_awaited_once_with(4242)
    context.bot.send_poll.assert_not_called()


@pytest.mark.asyncio
async def test_ai_response_empty_not_blocked_still_consumes_quota(monkeypatch):
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIResponseEmpty(blocked=False)))

    await quiz.handle_quiz_text_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(quiz._EMPTY_RESPONSE_MESSAGE)
    quiz_usage_repository.increment_quiz_usage.assert_awaited_once_with(4242)


@pytest.mark.asyncio
async def test_admin_ai_response_empty_does_not_consume_quota(monkeypatch):
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIResponseEmpty(blocked=True)))

    await quiz.handle_quiz_text_message(update, context)

    quiz_usage_repository.increment_quiz_usage.assert_not_called()


@pytest.mark.asyncio
async def test_logs_feature_usage_with_model_detail(monkeypatch):
    from bme_bot.db import feature_usage_repository

    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=(_valid_quiz_json(), "groq/qwen/qwen3.6-27b")))
    log_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_mock)

    await quiz.handle_quiz_text_message(update, context)

    log_mock.assert_awaited_once_with(4242, "quiz", detail="groq/qwen/qwen3.6-27b")


@pytest.mark.asyncio
async def test_archives_every_generated_question_with_model_and_user(monkeypatch):
    """رگرسیون: هر سوال تولیدشده باید آرشیو بشه — نه فقط اولی، نه فقط
    یه شمارنده‌ی کلی — دقیقاً همون content که واقعاً به‌عنوان poll
    فرستاده می‌شه، هرکدوم با user_id و مدل درست."""
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=(_valid_quiz_json(count=3), "groq/model-x")))
    archive_mock = AsyncMock()
    monkeypatch.setattr(quiz_archive, "archive_quiz", archive_mock)

    await quiz.handle_quiz_text_message(update, context)

    archive_mock.assert_awaited_once()
    call_args = archive_mock.await_args
    assert call_args.args[0] == 4242  # user_id
    archived_questions = call_args.args[1]
    assert len(archived_questions) == 3
    assert archived_questions[0]["question"] == quiz._parse_and_validate_quiz(_valid_quiz_json(count=1))[0]["question"]
    assert call_args.args[2] == "groq/model-x"  # model_used


@pytest.mark.asyncio
async def test_archive_quiz_swallows_write_failures_instead_of_raising(monkeypatch):
    """آرشیو یه کار جانبیِ best-effort است — quiz.py هیچ try/except دور
    فراخوانی archive_quiz ندارد و نباید داشته باشد، چون خودِ این تابع
    مسئول قورت‌دادن خطای نوشتن است (نه بالا فرستادنش)، دقیقاً برای اینکه
    یه دیسک پر یا مسیر غیرقابل‌نوشتن هیچ‌وقت جلوی ارسال واقعی کوییز به
    کاربر رو نگیره."""
    monkeypatch.setattr(config, "QUIZ_ARCHIVE_PATH", "/this/path/does/not/exist/archive.jsonl")
    q = quiz._parse_and_validate_quiz(_valid_quiz_json(count=1))

    await _real_archive_quiz(user_id=1, questions=q, model_used="model-a")  # نباید raise کنه


@pytest.mark.asyncio
async def test_archive_quiz_writes_valid_jsonl_end_to_end(tmp_path, monkeypatch):
    """بدون هیچ mock ای روی خودِ quiz_archive — فایل واقعی رو می‌نویسه و
    می‌خونتش، برای اطمینان از فرمت واقعی خروجی (نه فقط اینکه تابع صدا
    زده شده)."""
    monkeypatch.setattr(config, "QUIZ_ARCHIVE_PATH", str(tmp_path / "archive.jsonl"))

    questions = quiz._parse_and_validate_quiz(_valid_quiz_json(count=2))
    await _real_archive_quiz(user_id=4242, questions=questions, model_used="gemini/gemini-3.6-flash")

    with open(config.QUIZ_ARCHIVE_PATH, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

    assert len(lines) == 2
    for entry in lines:
        assert entry["user_id"] == 4242
        assert entry["model"] == "gemini/gemini-3.6-flash"
        assert entry["question"] == _VALID_QUESTION["question"]
        assert entry["options"] == _VALID_QUESTION["options"]
        assert entry["correct_index"] == _VALID_QUESTION["correct_index"]
        assert "timestamp" in entry


@pytest.mark.asyncio
async def test_archive_quiz_appends_across_multiple_calls_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "QUIZ_ARCHIVE_PATH", str(tmp_path / "archive.jsonl"))
    q = quiz._parse_and_validate_quiz(_valid_quiz_json(count=1))

    await _real_archive_quiz(user_id=1, questions=q, model_used="model-a")
    await _real_archive_quiz(user_id=2, questions=q, model_used="model-b")

    with open(config.QUIZ_ARCHIVE_PATH, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

    assert len(lines) == 2
    assert [entry["user_id"] for entry in lines] == [1, 2]


def test_tools_menu_includes_quiz_button():
    from bme_bot.keyboards import reply_keyboards

    rendered = {btn.text for row in reply_keyboards.TOOLS_MENU_BUTTONS for btn in row}
    assert reply_keyboards.QUIZ_TOOL_TEXT in rendered


def test_tools_menu_includes_random_quiz_button():
    from bme_bot.keyboards import reply_keyboards

    rendered = {btn.text for row in reply_keyboards.TOOLS_MENU_BUTTONS for btn in row}
    assert reply_keyboards.RANDOM_QUIZ_TOOL_TEXT in rendered
    assert reply_keyboards.RANDOM_QUIZ_TOOL_TEXT in reply_keyboards.ALL_MENU_BUTTON_TEXTS


# --- quiz_archive.get_random_question ---

@pytest.mark.asyncio
async def test_get_random_question_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "QUIZ_ARCHIVE_PATH", str(tmp_path / "does_not_exist.jsonl"))

    assert await quiz_archive.get_random_question() is None


@pytest.mark.asyncio
async def test_get_random_question_returns_none_when_file_empty(tmp_path, monkeypatch):
    path = tmp_path / "archive.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "QUIZ_ARCHIVE_PATH", str(path))

    assert await quiz_archive.get_random_question() is None


@pytest.mark.asyncio
async def test_get_random_question_returns_a_valid_entry(tmp_path, monkeypatch):
    path = tmp_path / "archive.jsonl"
    monkeypatch.setattr(config, "QUIZ_ARCHIVE_PATH", str(path))
    q = quiz._parse_and_validate_quiz(_valid_quiz_json(count=1))
    await _real_archive_quiz(user_id=1, questions=q, model_used="model-a")

    result = await quiz_archive.get_random_question()

    assert result is not None
    assert result["question"] == _VALID_QUESTION["question"]
    assert result["options"] == _VALID_QUESTION["options"]
    assert result["correct_index"] == _VALID_QUESTION["correct_index"]


@pytest.mark.asyncio
async def test_get_random_question_skips_malformed_lines(tmp_path, monkeypatch):
    """یک خط JSON نامعتبر (مثلاً از یه نوشتن قطع‌شده) و یک خط با schema
    ناقص (فاقد یکی از فیلدهای لازم) نباید کل عملیات رو خراب کنن — تابع
    باید ازشون رد بشه و همچنان ردیف معتبر بعدی رو برگردونه."""
    path = tmp_path / "archive.jsonl"
    lines = [
        "{not valid json",
        json.dumps({"question": "ناقص", "options": ["الف"]}, ensure_ascii=False),  # فیلد کم
        json.dumps(
            {
                "timestamp": "2026-01-01 00:00:00", "user_id": 1, "model": "m",
                **_VALID_QUESTION,
            },
            ensure_ascii=False,
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(config, "QUIZ_ARCHIVE_PATH", str(path))

    result = await quiz_archive.get_random_question()

    assert result is not None
    assert result["question"] == _VALID_QUESTION["question"]


# --- معافیت کامل ادمین ---

@pytest.mark.asyncio
async def test_admin_skips_limit_check_entirely(monkeypatch):
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    check_mock = AsyncMock(side_effect=AssertionError("ادمین نباید اصلاً چک بشه"))
    monkeypatch.setattr(quiz_usage_repository, "check_quiz_limit", check_mock)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=(_valid_quiz_json(), "gemini/gemini-2.5-flash")))

    await quiz.handle_quiz_text_message(update, context)

    check_mock.assert_not_called()


@pytest.mark.asyncio
async def test_admin_does_not_consume_usage_quota(monkeypatch):
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=(_valid_quiz_json(), "gemini/gemini-2.5-flash")))

    await quiz.handle_quiz_text_message(update, context)

    quiz_usage_repository.record_attempt.assert_not_called()
    quiz_usage_repository.increment_quiz_usage.assert_not_called()


# ------------------------------- فاز Q1: انتخاب تعداد سوال -------------------------------

def test_question_count_markup_has_all_ten_options_split_two_rows():
    markup = quiz._question_count_markup()
    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    assert [btn.text for btn in all_buttons] == [str(n) for n in range(2, 11)]
    assert [btn.callback_data for btn in all_buttons] == [f"quiz_count:{n}" for n in range(2, 11)]
    assert len(markup.inline_keyboard) == 2


def test_format_prompt_replaces_placeholder_with_chosen_count():
    formatted = quiz._format_prompt(7)
    assert "__QUESTION_COUNT__" not in formatted
    assert "دقیقاً 7 سوال" in formatted


def test_format_prompt_does_not_corrupt_json_example_braces():
    """پرامپت خودش یه مثال JSON با آکولاد واقعی داره — چون substitution با
    replace() انجام می‌شه نه str.format()، نباید بشکنه."""
    formatted = quiz._format_prompt(5)
    assert '"question": "متن سوال"' in formatted


def _fake_query(data):
    return SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock())


@pytest.mark.asyncio
async def test_quiz_count_callback_valid_count_sets_state_and_prompts():
    query = _fake_query("quiz_count:7")
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={})

    await quiz.handle_quiz_count_callback(update, context, query.data)

    assert context.user_data == {"quiz_question_count": 7, "awaiting_quiz_text": True}
    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once_with(quiz._PROMPT_FOR_TEXT_MESSAGE)


@pytest.mark.asyncio
async def test_quiz_count_callback_rejects_out_of_range_count():
    query = _fake_query("quiz_count:99")
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={})

    await quiz.handle_quiz_count_callback(update, context, query.data)

    assert context.user_data == {}
    query.answer.assert_awaited_once_with(quiz._INVALID_COUNT_MESSAGE, show_alert=True)
    query.edit_message_text.assert_not_called()


@pytest.mark.asyncio
async def test_quiz_count_callback_rejects_malformed_data():
    query = _fake_query("quiz_count:not_a_number")
    update = SimpleNamespace(callback_query=query)
    context = SimpleNamespace(user_data={})

    await quiz.handle_quiz_count_callback(update, context, query.data)

    assert context.user_data == {}
    assert query.answer.await_args.kwargs["show_alert"] is True


@pytest.mark.asyncio
async def test_chosen_question_count_flows_into_the_prompt_sent_to_ai(monkeypatch):
    """سرتاسری: انتخاب ۳ سوال باید همون عددی باشه که در پرامپت واقعی
    فرستاده‌شده به ai_service.ask جایگزین __QUESTION_COUNT__ شده."""
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True, "quiz_question_count": 3})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    ask_mock = AsyncMock(return_value=(_valid_quiz_json(count=3), "gemini/gemini-2.5-flash"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await quiz.handle_quiz_text_message(update, context)

    sent_prompt = ask_mock.await_args.args[1]
    assert "دقیقاً 3 سوال" in sent_prompt
    assert "quiz_question_count" not in context.user_data


@pytest.mark.asyncio
async def test_missing_question_count_falls_back_to_default(monkeypatch):
    """محافظ دفاعی: اگر به هر دلیلی quiz_question_count ست نشده باشه (نباید
    عملاً پیش بیاید)، باید به همون ۵ قبلی برگرده، نه کرش کنه."""
    update, message = _make_update_with_text()
    context = _make_context(user_data={"awaiting_quiz_text": True})  # بدون quiz_question_count
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    ask_mock = AsyncMock(return_value=(_valid_quiz_json(), "gemini/gemini-2.5-flash"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await quiz.handle_quiz_text_message(update, context)

    sent_prompt = ask_mock.await_args.args[1]
    assert "دقیقاً 5 سوال" in sent_prompt


# ------------------------------- فاز Q1: استخراج متن فایل -------------------------------

def test_get_extension_lowercases_and_strips_dot():
    assert quiz._get_extension("Notes.DOCX") == "docx"
    assert quiz._get_extension("plain.txt") == "txt"


def test_get_extension_handles_no_extension_or_missing_filename():
    assert quiz._get_extension("no_extension_file") == ""
    assert quiz._get_extension(None) == ""
    assert quiz._get_extension("") == ""


def test_extract_text_from_txt_bytes_decodes_utf8():
    text = quiz._extract_text_from_bytes("متن آزمایشی".encode("utf-8"), "txt")
    assert text == "متن آزمایشی"


def test_extract_text_from_txt_bytes_replaces_invalid_encoding_instead_of_crashing():
    text = quiz._extract_text_from_bytes(b"\xff\xfe\x00broken", "txt")
    assert isinstance(text, str)  # errors="replace" نباید کرش کنه


def test_extract_text_from_valid_docx_bytes():
    docx_bytes = _make_minimal_docx(["پاراگراف اول", "پاراگراف دوم"])
    text = quiz._extract_text_from_bytes(docx_bytes, "docx")
    assert "پاراگراف اول" in text
    assert "پاراگراف دوم" in text


def test_extract_text_from_garbage_bytes_as_docx_raises_extraction_failed():
    with pytest.raises(quiz.DocumentExtractionFailed):
        quiz._extract_text_from_bytes(b"this is not a zip file at all", "docx")


def test_extract_text_from_valid_zip_but_not_a_docx_structure_raises_extraction_failed():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("hello.txt", "not a docx internal structure")
    with pytest.raises(quiz.DocumentExtractionFailed):
        quiz._extract_text_from_bytes(buf.getvalue(), "docx")


def test_extract_text_unsupported_extension_raises():
    with pytest.raises(quiz.UnsupportedDocumentFormat):
        quiz._extract_text_from_bytes(b"anything", "pdf")


# ------------------------------- فاز Q1: هندلر فایل آپلودی -------------------------------

def _make_document_update(
    filename="notes.docx", file_size=1000, file_id="file123", text_content=None, chat_id=777, user_id=4242,
):
    document = SimpleNamespace(file_name=filename, file_size=file_size, file_id=file_id)
    message = SimpleNamespace(document=document, reply_text=AsyncMock())
    update = SimpleNamespace(
        message=message, effective_user=SimpleNamespace(id=user_id), effective_chat=SimpleNamespace(id=chat_id),
    )
    return update, message


def _make_document_context(user_data=None, download_bytes=b""):
    telegram_file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(download_bytes)))
    bot = SimpleNamespace(get_file=AsyncMock(return_value=telegram_file), send_poll=AsyncMock())
    return SimpleNamespace(user_data=user_data if user_data is not None else {}, bot=bot)


@pytest.mark.asyncio
async def test_document_ignored_when_not_awaiting_quiz_text():
    update, message = _make_document_update()
    context = _make_document_context(user_data={})

    await quiz.handle_quiz_document_message(update, context)

    message.reply_text.assert_not_called()
    context.bot.get_file.assert_not_called()


@pytest.mark.asyncio
async def test_txt_document_generates_quiz_successfully(monkeypatch):
    update, message = _make_document_update(filename="notes.txt", file_size=20)
    context = _make_document_context(
        user_data={"awaiting_quiz_text": True, "quiz_question_count": 5},
        download_bytes="یه متن درسی کوتاه.".encode("utf-8"),
    )
    processing_msg = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(admin_utils, "is_admin", lambda uid: False)
    monkeypatch.setattr(quiz_usage_repository, "check_quiz_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(quiz_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(quiz_usage_repository, "increment_quiz_usage", AsyncMock())
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key")
    ask_mock = AsyncMock(return_value=(_valid_quiz_json(), "gemini/gemini-2.5-flash"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await quiz.handle_quiz_document_message(update, context)

    assert ask_mock.await_args.args[0] == "یه متن درسی کوتاه."
    assert context.bot.send_poll.await_count == 5
    assert "awaiting_quiz_text" not in context.user_data


@pytest.mark.asyncio
async def test_docx_document_generates_quiz_successfully(monkeypatch):
    docx_bytes = _make_minimal_docx(["نکته‌ی درسی اول", "نکته‌ی درسی دوم"])
    update, message = _make_document_update(filename="جزوه.docx", file_size=len(docx_bytes))
    context = _make_document_context(
        user_data={"awaiting_quiz_text": True, "quiz_question_count": 2}, download_bytes=docx_bytes,
    )
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda uid: False)
    monkeypatch.setattr(quiz_usage_repository, "check_quiz_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(quiz_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(quiz_usage_repository, "increment_quiz_usage", AsyncMock())
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key")
    ask_mock = AsyncMock(return_value=(_valid_quiz_json(count=2), "gemini/gemini-2.5-flash"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await quiz.handle_quiz_document_message(update, context)

    sent_text = ask_mock.await_args.args[0]
    assert "نکته‌ی درسی اول" in sent_text
    assert "نکته‌ی درسی دوم" in sent_text
    assert "دقیقاً 2 سوال" in ask_mock.await_args.args[1]


@pytest.mark.asyncio
async def test_unsupported_extension_rejected_without_downloading():
    update, message = _make_document_update(filename="slides.pptx")
    context = _make_document_context(user_data={"awaiting_quiz_text": True})

    await quiz.handle_quiz_document_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(quiz._UNSUPPORTED_FORMAT_MESSAGE)


@pytest.mark.asyncio
async def test_legacy_doc_extension_gets_specific_message():
    update, message = _make_document_update(filename="old_notes.doc")
    context = _make_document_context(user_data={"awaiting_quiz_text": True})

    await quiz.handle_quiz_document_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(quiz._LEGACY_DOC_MESSAGE)


@pytest.mark.asyncio
async def test_oversized_file_size_metadata_rejected_without_downloading():
    update, message = _make_document_update(filename="huge.docx", file_size=quiz._MAX_DOWNLOAD_BYTES + 1)
    context = _make_document_context(user_data={"awaiting_quiz_text": True})

    await quiz.handle_quiz_document_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(quiz._FILE_TOO_LARGE_MESSAGE)


@pytest.mark.asyncio
async def test_oversized_actual_download_rejected_even_if_metadata_missing():
    """محافظ دفاعی دوم: اگر file_size متادیتا صفر/غایب باشه ولی بایت واقعی
    دانلودشده بزرگ باشه، بعد از دانلود هم چک بشه (هم‌الگو با jozve.py)."""
    update, message = _make_document_update(filename="huge.txt", file_size=0)
    oversized_bytes = b"a" * (quiz._MAX_DOWNLOAD_BYTES + 1)
    context = _make_document_context(user_data={"awaiting_quiz_text": True}, download_bytes=oversized_bytes)

    await quiz.handle_quiz_document_message(update, context)

    message.reply_text.assert_awaited_once_with(quiz._FILE_TOO_LARGE_MESSAGE)


@pytest.mark.asyncio
async def test_corrupt_docx_shows_friendly_extraction_error():
    update, message = _make_document_update(filename="corrupt.docx", file_size=100)
    context = _make_document_context(user_data={"awaiting_quiz_text": True}, download_bytes=b"not a real docx")

    await quiz.handle_quiz_document_message(update, context)

    message.reply_text.assert_awaited_once_with(quiz._EXTRACTION_FAILED_MESSAGE)


@pytest.mark.asyncio
async def test_extracted_text_over_length_cap_rejected_without_calling_ai(monkeypatch):
    long_text = "الف " * 2000  # قطعاً بیشتر از سقف ۴۰۹۶ کاراکتر
    update, message = _make_document_update(filename="long.txt", file_size=len(long_text))
    context = _make_document_context(
        user_data={"awaiting_quiz_text": True}, download_bytes=long_text.encode("utf-8"),
    )
    ask_mock = AsyncMock(side_effect=AssertionError("ask نباید صدا زده بشه"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await quiz.handle_quiz_document_message(update, context)

    ask_mock.assert_not_called()
    sent_message = message.reply_text.await_args.args[0]
    assert "طولانیه" in sent_message
    assert str(quiz._MAX_UPLOADED_TEXT_LENGTH) in sent_message


@pytest.mark.asyncio
async def test_empty_extracted_text_shows_empty_response_message():
    update, message = _make_document_update(filename="empty.txt", file_size=0)
    context = _make_document_context(user_data={"awaiting_quiz_text": True}, download_bytes=b"   ")

    await quiz.handle_quiz_document_message(update, context)

    message.reply_text.assert_awaited_once_with(quiz._EMPTY_RESPONSE_MESSAGE)


@pytest.mark.asyncio
async def test_document_path_respects_daily_limit(monkeypatch):
    update, message = _make_document_update(filename="notes.txt", file_size=10)
    context = _make_document_context(
        user_data={"awaiting_quiz_text": True}, download_bytes="متن کوتاه".encode("utf-8"),
    )
    monkeypatch.setattr(admin_utils, "is_admin", lambda uid: False)
    monkeypatch.setattr(
        quiz_usage_repository, "check_quiz_limit",
        AsyncMock(return_value=(False, "شما از تمام 5 کوییز روزانه‌ی خود استفاده کرده‌اید.")),
    )
    ask_mock = AsyncMock(side_effect=AssertionError("ask نباید صدا زده بشه"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await quiz.handle_quiz_document_message(update, context)

    ask_mock.assert_not_called()
    message.reply_text.assert_awaited_once_with("⚠️ شما از تمام 5 کوییز روزانه‌ی خود استفاده کرده‌اید.")


# --- handle_random_quiz_selected ---

def _make_random_quiz_update():
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=4242),
        effective_chat=SimpleNamespace(id=777),
    )
    return update, message


@pytest.mark.asyncio
async def test_random_quiz_sends_empty_archive_message_when_no_questions(monkeypatch):
    update, message = _make_random_quiz_update()
    context = _make_context()
    monkeypatch.setattr(quiz_archive, "get_random_question", AsyncMock(return_value=None))

    await quiz.handle_random_quiz_selected(update, context)

    message.reply_text.assert_awaited_once_with(quiz._EMPTY_ARCHIVE_MESSAGE)
    context.bot.send_poll.assert_not_called()


@pytest.mark.asyncio
async def test_random_quiz_sends_poll_and_logs_usage_when_question_exists(monkeypatch):
    from bme_bot.db import feature_usage_repository

    update, message = _make_random_quiz_update()
    context = _make_context()
    monkeypatch.setattr(quiz_archive, "get_random_question", AsyncMock(return_value=dict(_VALID_QUESTION)))
    log_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_mock)

    await quiz.handle_random_quiz_selected(update, context)

    message.reply_text.assert_not_called()
    context.bot.send_poll.assert_awaited_once_with(
        chat_id=777,
        question=_VALID_QUESTION["question"],
        options=_VALID_QUESTION["options"],
        type=Poll.QUIZ,
        correct_option_id=_VALID_QUESTION["correct_index"],
        explanation=_VALID_QUESTION["explanation"],
        is_anonymous=True,
    )
    log_mock.assert_awaited_once_with(4242, "quiz_random")


@pytest.mark.asyncio
async def test_random_quiz_never_touches_daily_limit_repository(monkeypatch):
    """تصمیم عمدی: کوییز تصادفی هیچ بودجه‌ی AI مصرف نمی‌کنه، پس نباید هیچ
    کاری با quiz_usage_repository (نه چک، نه ثبت) داشته باشه — نه برای
    ادمین، نه برای کاربر عادی. این تست همون تصمیم رو قفل می‌کنه تا یه
    تغییر بعدی سهوی سقف روزانه رو اینجا هم اعمال نکنه."""
    update, message = _make_random_quiz_update()
    context = _make_context()
    monkeypatch.setattr(quiz_archive, "get_random_question", AsyncMock(return_value=dict(_VALID_QUESTION)))
    monkeypatch.setattr(admin_utils, "is_admin", lambda uid: False)
    check_mock = AsyncMock(side_effect=AssertionError("نباید صدا زده بشه"))
    monkeypatch.setattr(quiz_usage_repository, "check_quiz_limit", check_mock)

    await quiz.handle_random_quiz_selected(update, context)

    check_mock.assert_not_called()
