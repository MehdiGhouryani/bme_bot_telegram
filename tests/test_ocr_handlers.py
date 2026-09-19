# tests/test_ocr_handlers.py
#
# تست‌های هندلر OCR: مدیریت پرچم awaiting_ocr_image، عدم تداخل با
# عکس‌های نامرتبط، و مسیر کامل موفق/ناموفق.
#
# محدودیت روزانه/کول‌داون OCR: برای این‌که تست‌های قبلی (که موضوع‌شان مسیر
# OCR است، نه رفتار محدودیت) نیازی به دست‌کاری جداگانه نداشته باشند، یک
# fixture با autouse=True پیش‌فرض «همیشه مجاز» را برای
# ocr_service.is_configured/ocr_usage_repository.check_ocr_limit/record_attempt/
# increment_ocr_usage ست می‌کند؛ تست‌های اختصاصی محدودیت (پایین فایل) این
# پیش‌فرض را خودشان override می‌کنند.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.db import ocr_usage_repository  # noqa: E402
from bme_bot.handlers import ocr  # noqa: E402
from bme_bot.services import ocr_service  # noqa: E402
from bme_bot.utils import admin as admin_utils  # noqa: E402
from bme_bot.utils import error_reporting, messages  # noqa: E402


@pytest.fixture(autouse=True)
def _allow_ocr_by_default(monkeypatch):
    """پیش‌فرض این فایل: OCR پیکربندی‌شده، کاربر عادی (نه ادمین) هنوز به
    سقف نخورده — تست‌های مسیر اصلی (موفق/ناموفق OCR) نیازی به تکرار این
    mock ندارند."""
    monkeypatch.setattr(ocr_service, "is_configured", lambda: True)
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: False)
    monkeypatch.setattr(ocr_usage_repository, "check_ocr_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(ocr_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(ocr_usage_repository, "increment_ocr_usage", AsyncMock())


def _make_update_with_photo():
    message = SimpleNamespace(
        photo=[SimpleNamespace(file_id="small"), SimpleNamespace(file_id="large")],
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=4242))
    return update, message


def _make_context(user_data=None):
    telegram_file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"fake-bytes")))
    bot = SimpleNamespace(get_file=AsyncMock(return_value=telegram_file))
    return SimpleNamespace(user_data=user_data if user_data is not None else {}, bot=bot)


@pytest.mark.asyncio
async def test_photo_ignored_when_not_awaiting_ocr_image():
    update, message = _make_update_with_photo()
    context = _make_context(user_data={})

    await ocr.handle_photo_message(update, context)

    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_photo_clears_awaiting_flag_even_before_processing():
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))

    await ocr.handle_photo_message(update, context)

    assert "awaiting_ocr_image" not in context.user_data


@pytest.mark.asyncio
async def test_photo_uses_largest_resolution(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))
    monkeypatch.setattr(
        ocr_service, "extract_text", AsyncMock(return_value=ocr_service.OcrResult(text="سلام", provider="google"))
    )

    await ocr.handle_photo_message(update, context)

    context.bot.get_file.assert_awaited_once_with("large")


@pytest.mark.asyncio
async def test_photo_successful_ocr_sends_normalized_text(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        ocr_service,
        "extract_text",
        AsyncMock(return_value=ocr_service.OcrResult(text="كتاب علمي", provider="google")),
    )

    await ocr.handle_photo_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with("کتاب علمی")


@pytest.mark.asyncio
async def test_photo_no_text_found_shows_friendly_message(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        ocr_service, "extract_text", AsyncMock(return_value=ocr_service.OcrResult(text="", provider=None))
    )

    await ocr.handle_photo_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(ocr._NO_TEXT_FOUND_MESSAGE)


@pytest.mark.asyncio
async def test_photo_service_unavailable_shows_specific_message(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        ocr_service,
        "extract_text",
        AsyncMock(side_effect=ocr_service.OcrServiceUnavailable("no keys")),
    )
    # این مسیر باید یک هشدار به ادمین بدهد.
    report_issue_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_issue_mock)

    await ocr.handle_photo_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(messages.OCR_UNAVAILABLE)
    report_issue_mock.assert_awaited_once()
    _, kwargs = report_issue_mock.call_args
    assert kwargs["failure_feature"] == "ocr"
    assert kwargs["user_id"] == 4242


@pytest.mark.asyncio
async def test_photo_unexpected_error_is_caught_and_reported_generically(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(ocr_service, "extract_text", AsyncMock(side_effect=RuntimeError("boom")))
    # این مسیر هم باید یک هشدار به ادمین بدهد (نه فقط logger.exception محلی).
    report_error_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_error", report_error_mock)

    await ocr.handle_photo_message(update, context)  # نباید استثنا بالا بیاید

    processing_msg.edit_text.assert_awaited_once_with(ocr._GENERIC_ERROR_MESSAGE)
    report_error_mock.assert_awaited_once()
    _, kwargs = report_error_mock.call_args
    assert kwargs["failure_feature"] == "ocr"
    assert kwargs["user_id"] == 4242


@pytest.mark.asyncio
async def test_long_ocr_result_is_split_into_multiple_messages(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)

    long_text = "الف" * 3000  # طولانی‌تر از سقف ۴۰۹۶ کاراکتر تلگرام
    monkeypatch.setattr(
        ocr_service, "extract_text", AsyncMock(return_value=ocr_service.OcrResult(text=long_text, provider="google"))
    )

    await ocr.handle_photo_message(update, context)

    processing_msg.edit_text.assert_awaited_once()
    # چون آماده‌سازی اولین پیام «⏳ در حال...» با reply_text بود، تکه‌ی دوم هم
    # باید با reply_text ارسال شده باشد (نه edit_text) — یعنی reply_text باید
    # حداقل دوبار صدا زده شده باشد (یک‌بار پیام «در حال پردازش»، یک‌بار تکه‌ی دوم).
    assert message.reply_text.await_count >= 2


@pytest.mark.asyncio
async def test_tools_menu_shown_on_button_press():
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace()

    await ocr.handle_tools_menu(update, context)

    message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_ocr_tool_selected_sets_awaiting_flag_and_prompts():
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={})

    await ocr.handle_ocr_tool_selected(update, context)

    assert context.user_data["awaiting_ocr_image"] is True
    message.reply_text.assert_awaited_once_with(ocr._PROMPT_FOR_PHOTO_MESSAGE)


# --- تست‌های محدودیت روزانه/کول‌داون + تمایز خطای واقعی از «متن نبود» ---

@pytest.mark.asyncio
async def test_photo_rejected_when_ocr_not_configured_before_download(monkeypatch):
    """پیش‌چک is_configured() باید *قبل* از دانلود عکس رد شود — یعنی
    context.bot.get_file اصلاً نباید صدا زده شود."""
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    monkeypatch.setattr(ocr_service, "is_configured", lambda: False)

    await ocr.handle_photo_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(messages.OCR_UNAVAILABLE)


@pytest.mark.asyncio
async def test_photo_rejected_when_daily_ocr_limit_reached(monkeypatch):
    """وقتی check_ocr_limit رد کند، extract_text نباید اصلاً صدا
    زده شود (یعنی هیچ فراخوانی واقعی به Google/Azure/Groq نمی‌رود)."""
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    monkeypatch.setattr(
        ocr_usage_repository, "check_ocr_limit",
        AsyncMock(return_value=(False, "شما از تمام 5 تبدیل عکس روزانه‌ی خود استفاده کرده‌اید.")),
    )
    extract_mock = AsyncMock(side_effect=AssertionError("extract_text نباید صدا زده شود"))
    monkeypatch.setattr(ocr_service, "extract_text", extract_mock)

    await ocr.handle_photo_message(update, context)

    extract_mock.assert_not_called()
    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with("⚠️ شما از تمام 5 تبدیل عکس روزانه‌ی خود استفاده کرده‌اید.")


@pytest.mark.asyncio
async def test_photo_provider_error_shows_distinct_message_and_skips_usage_increment(monkeypatch):
    """OcrProviderError نباید با «متنی پیدا نشد» یکی گرفته شود، و چون حداقل
    یک لایه خطای واقعی داده، سهمیه‌ی روزانه نباید کم شود — کول‌داون (record_attempt)
    اما باید همچنان ثبت شده باشد."""
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        ocr_service, "extract_text",
        AsyncMock(side_effect=ocr_service.OcrProviderError("google failed with 500")),
    )
    # این مسیر هم باید یک هشدار به ادمین بدهد.
    report_issue_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_issue_mock)

    await ocr.handle_photo_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(ocr._PROVIDER_ERROR_MESSAGE)
    ocr_usage_repository.record_attempt.assert_awaited_once_with(4242)
    ocr_usage_repository.increment_ocr_usage.assert_not_called()
    report_issue_mock.assert_awaited_once()
    args, kwargs = report_issue_mock.call_args
    assert "google failed with 500" in args[1]
    assert kwargs["failure_feature"] == "ocr"


@pytest.mark.asyncio
async def test_photo_increments_usage_after_successful_processing_with_text(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        ocr_service, "extract_text",
        AsyncMock(return_value=ocr_service.OcrResult(text="متن یافت‌شده", provider="google")),
    )

    await ocr.handle_photo_message(update, context)

    ocr_usage_repository.increment_ocr_usage.assert_awaited_once_with(4242)


@pytest.mark.asyncio
async def test_photo_increments_usage_even_when_genuinely_no_text_found(monkeypatch):
    """تفاوت کلیدی: برخلاف AI (که فقط پاسخ *مفید* سهمیه می‌سوزاند)،
    اینجا «واقعاً متنی نبود» (بدون خطا) هم باید سهمیه بسوزاند — چون سرویس‌های
    خارجی واقعاً و بی‌خطا فراخوانی شدند؛ فقط خطای واقعی provider سهمیه‌سوز
    نیست (تست بالا)."""
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        ocr_service, "extract_text",
        AsyncMock(return_value=ocr_service.OcrResult(text="", provider=None)),
    )

    await ocr.handle_photo_message(update, context)

    ocr_usage_repository.increment_ocr_usage.assert_awaited_once_with(4242)


@pytest.mark.asyncio
async def test_photo_logs_feature_usage_with_provider_detail(monkeypatch):
    """detail باید دقیقاً همان provider ای باشد که ocr_service
    برگردانده — برای بخش «سلامت سیستم» پنل ادمین."""
    from bme_bot.db import feature_usage_repository

    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        ocr_service, "extract_text",
        AsyncMock(return_value=ocr_service.OcrResult(text="متن یافت‌شده", provider="groq_vision")),
    )
    log_usage_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_usage_mock)

    await ocr.handle_photo_message(update, context)

    log_usage_mock.assert_awaited_once_with(4242, "ocr", detail="groq_vision")


# --- معافیت کامل ادمین ---

@pytest.mark.asyncio
async def test_admin_skips_limit_check_entirely(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    check_mock = AsyncMock(side_effect=AssertionError("ادمین نباید اصلاً چک بشه"))
    monkeypatch.setattr(ocr_usage_repository, "check_ocr_limit", check_mock)
    monkeypatch.setattr(
        ocr_service, "extract_text", AsyncMock(return_value=ocr_service.OcrResult(text="متن", provider="google"))
    )

    await ocr.handle_photo_message(update, context)

    check_mock.assert_not_called()


@pytest.mark.asyncio
async def test_admin_does_not_consume_usage_quota(monkeypatch):
    update, message = _make_update_with_photo()
    context = _make_context(user_data={"awaiting_ocr_image": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    monkeypatch.setattr(
        ocr_service, "extract_text", AsyncMock(return_value=ocr_service.OcrResult(text="متن", provider="google"))
    )

    await ocr.handle_photo_message(update, context)

    ocr_usage_repository.record_attempt.assert_not_called()
    ocr_usage_repository.increment_ocr_usage.assert_not_called()


# --- handle_group_ocr_request (بند ۵: Ephemeral Messages) ---

def _make_group_update_and_context():
    message = SimpleNamespace(
        photo=[SimpleNamespace(file_id="small"), SimpleNamespace(file_id="large")],
        message_id=777,
        reply_text=AsyncMock(return_value=SimpleNamespace(message_id=888)),
    )
    update = SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=4242),
        effective_chat=SimpleNamespace(id=-100999),
    )
    telegram_file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"fake-bytes")))
    bot = SimpleNamespace(
        get_file=AsyncMock(return_value=telegram_file),
        send_message=AsyncMock(),
        delete_message=AsyncMock(),
    )
    context = SimpleNamespace(bot=bot)
    return update, message, context


@pytest.mark.asyncio
async def test_group_ocr_caption_regex_matches_command_with_or_without_bot_mention():
    assert ocr.GROUP_OCR_CAPTION_REGEX.match("/ocr")
    assert ocr.GROUP_OCR_CAPTION_REGEX.match("/OCR")
    assert ocr.GROUP_OCR_CAPTION_REGEX.match("/ocr@my_bme_bot")
    assert ocr.GROUP_OCR_CAPTION_REGEX.match("/ocr این عکس رو بخون")
    assert not ocr.GROUP_OCR_CAPTION_REGEX.match("این /ocr نیست چون اول کپشن نیومده")
    assert not ocr.GROUP_OCR_CAPTION_REGEX.match("/ocrsomething")


@pytest.mark.asyncio
async def test_group_ocr_success_sends_result_ephemerally_and_cleans_up_processing_message(monkeypatch):
    update, message, context = _make_group_update_and_context()
    monkeypatch.setattr(
        ocr_service, "extract_text",
        AsyncMock(return_value=ocr_service.OcrResult(text="سلام دنیا", provider="google")),
    )

    await ocr.handle_group_ocr_request(update, context)

    # پیام «در حال پردازش» موقت باید حذف شده باشه.
    context.bot.delete_message.assert_awaited_once_with(chat_id=-100999, message_id=888)
    # نتیجه باید ephemeral (فقط برای user_id=4242) ارسال شده باشه.
    context.bot.send_message.assert_awaited_once()
    _, kwargs = context.bot.send_message.call_args
    assert kwargs["chat_id"] == -100999
    assert kwargs["api_kwargs"] == {"receiver_user_id": 4242}
    assert kwargs["text"] == "سلام دنیا"


@pytest.mark.asyncio
async def test_group_ocr_falls_back_to_visible_message_when_ephemeral_send_fails(monkeypatch):
    """رجوع به utils/ephemeral.py — قابلیت خیلی تازه‌ست، نباید جواب گم بشه."""
    update, message, context = _make_group_update_and_context()
    monkeypatch.setattr(
        ocr_service, "extract_text",
        AsyncMock(return_value=ocr_service.OcrResult(text="سلام دنیا", provider="google")),
    )
    context.bot.send_message = AsyncMock(side_effect=[Exception("ephemeral rejected"), None])

    await ocr.handle_group_ocr_request(update, context)

    assert context.bot.send_message.await_count == 2
    second_call = context.bot.send_message.await_args_list[1]
    assert "api_kwargs" not in second_call.kwargs
    assert second_call.kwargs["text"] == "سلام دنیا"


@pytest.mark.asyncio
async def test_group_ocr_rejected_when_daily_limit_reached_no_download_attempted(monkeypatch):
    update, message, context = _make_group_update_and_context()
    monkeypatch.setattr(
        ocr_usage_repository, "check_ocr_limit", AsyncMock(return_value=(False, "سقف روزانه تمام شد")),
    )

    await ocr.handle_group_ocr_request(update, context)

    context.bot.get_file.assert_not_called()
    context.bot.send_message.assert_awaited_once()
    _, kwargs = context.bot.send_message.call_args
    assert "سقف روزانه تمام شد" in kwargs["text"]
    assert kwargs["api_kwargs"] == {"receiver_user_id": 4242}


@pytest.mark.asyncio
async def test_group_ocr_admin_bypasses_daily_limit_and_usage_increment(monkeypatch):
    update, message, context = _make_group_update_and_context()
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    check_mock = AsyncMock()
    increment_mock = AsyncMock()
    monkeypatch.setattr(ocr_usage_repository, "check_ocr_limit", check_mock)
    monkeypatch.setattr(ocr_usage_repository, "increment_ocr_usage", increment_mock)
    monkeypatch.setattr(
        ocr_service, "extract_text",
        AsyncMock(return_value=ocr_service.OcrResult(text="سلام", provider="google")),
    )

    await ocr.handle_group_ocr_request(update, context)

    check_mock.assert_not_called()
    increment_mock.assert_not_called()


@pytest.mark.asyncio
async def test_group_ocr_logs_usage_under_distinct_feature_name(monkeypatch):
    """رجوع به کامنت داخل handle_group_ocr_request: «ocr_group» جدا از
    «ocr»، فقط برای آمار — سقف روزانه (بالاتر در همین تست فایل تست شده)
    کاملاً مستقل و مشترکه."""
    from bme_bot.db import feature_usage_repository

    update, message, context = _make_group_update_and_context()
    log_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_mock)
    monkeypatch.setattr(
        ocr_service, "extract_text",
        AsyncMock(return_value=ocr_service.OcrResult(text="سلام", provider="azure")),
    )

    await ocr.handle_group_ocr_request(update, context)

    log_mock.assert_awaited_once_with(4242, "ocr_group", detail="azure")


@pytest.mark.asyncio
async def test_group_ocr_provider_error_reports_and_sends_ephemeral_message(monkeypatch):
    update, message, context = _make_group_update_and_context()
    monkeypatch.setattr(
        ocr_service, "extract_text", AsyncMock(side_effect=ocr_service.OcrProviderError("all failed")),
    )
    report_issue_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_issue_mock)

    await ocr.handle_group_ocr_request(update, context)

    context.bot.delete_message.assert_awaited_once()
    report_issue_mock.assert_awaited_once()
    _, kwargs = context.bot.send_message.call_args
    assert kwargs["text"] == ocr._PROVIDER_ERROR_MESSAGE
