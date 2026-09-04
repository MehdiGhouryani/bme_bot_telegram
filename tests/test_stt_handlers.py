# tests/test_stt_handlers.py
#
# تست‌های هندلر STT: مدیریت پرچم awaiting_stt_voice، عدم تداخل با ویس‌های
# نامرتبط، و مسیر کامل موفق/ناموفق.
#
# duration_seconds از متادیتای voice خونده می‌شه و به
# check_stt_limit/increment_stt_usage پاس داده می‌شه؛ ادمین‌ها کامل معافن.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.db import stt_usage_repository  # noqa: E402
from bme_bot.handlers import stt  # noqa: E402
from bme_bot.services import stt_service  # noqa: E402
from bme_bot.utils import admin as admin_utils  # noqa: E402
from bme_bot.utils import error_reporting, messages  # noqa: E402

_DEFAULT_DURATION = 30


@pytest.fixture(autouse=True)
def _allow_stt_by_default(monkeypatch):
    """پیش‌فرض این فایل: STT پیکربندی‌شده، کاربر عادی (نه ادمین) هنوز به
    سقف نخورده."""
    monkeypatch.setattr(stt_service, "is_configured", lambda: True)
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: False)
    monkeypatch.setattr(stt_usage_repository, "check_stt_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(stt_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(stt_usage_repository, "increment_stt_usage", AsyncMock())


def _make_update_with_voice(duration=_DEFAULT_DURATION):
    message = SimpleNamespace(
        voice=SimpleNamespace(file_id="voice-file-id", duration=duration),
        reply_text=AsyncMock(),
    )
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=4242))
    return update, message


def _make_context(user_data=None):
    telegram_file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"fake-audio-bytes")))
    bot = SimpleNamespace(get_file=AsyncMock(return_value=telegram_file))
    return SimpleNamespace(user_data=user_data if user_data is not None else {}, bot=bot)


@pytest.mark.asyncio
async def test_voice_ignored_when_not_awaiting_stt_voice():
    update, message = _make_update_with_voice()
    context = _make_context(user_data={})

    await stt.handle_voice_message(update, context)

    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_voice_clears_awaiting_flag_even_before_processing():
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))

    await stt.handle_voice_message(update, context)

    assert "awaiting_stt_voice" not in context.user_data


@pytest.mark.asyncio
async def test_voice_downloads_file_by_id(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="سلام", provider="groq"))
    )

    await stt.handle_voice_message(update, context)

    context.bot.get_file.assert_awaited_once_with("voice-file-id")


@pytest.mark.asyncio
async def test_voice_successful_stt_sends_normalized_text(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(return_value=stt_service.SttResult(text="كتاب علمي", provider="groq")),
    )

    await stt.handle_voice_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with("کتاب علمی")


@pytest.mark.asyncio
async def test_voice_no_text_found_shows_friendly_message(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="", provider=None))
    )

    await stt.handle_voice_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(stt._NO_TEXT_FOUND_MESSAGE)


@pytest.mark.asyncio
async def test_voice_service_unavailable_shows_specific_message_and_alerts_admin(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(side_effect=stt_service.SttServiceUnavailable("no keys")),
    )
    report_issue_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_issue_mock)

    await stt.handle_voice_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(messages.STT_UNAVAILABLE)
    report_issue_mock.assert_awaited_once()
    _, kwargs = report_issue_mock.call_args
    assert kwargs["failure_feature"] == "stt"
    assert kwargs["user_id"] == 4242


@pytest.mark.asyncio
async def test_voice_unexpected_error_is_caught_and_reported_generically(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(stt_service, "transcribe", AsyncMock(side_effect=RuntimeError("boom")))
    report_error_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_error", report_error_mock)

    await stt.handle_voice_message(update, context)  # نباید استثنا بالا بیاید

    processing_msg.edit_text.assert_awaited_once_with(stt._GENERIC_ERROR_MESSAGE)
    report_error_mock.assert_awaited_once()
    _, kwargs = report_error_mock.call_args
    assert kwargs["failure_feature"] == "stt"
    assert kwargs["user_id"] == 4242


@pytest.mark.asyncio
async def test_long_stt_result_is_split_into_multiple_messages(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)

    long_text = "الف" * 3000  # طولانی‌تر از سقف ۴۰۹۶ کاراکتر تلگرام
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(return_value=stt_service.SttResult(text=long_text, provider="groq")),
    )

    await stt.handle_voice_message(update, context)

    processing_msg.edit_text.assert_awaited_once()
    assert message.reply_text.await_count >= 2


@pytest.mark.asyncio
async def test_stt_tool_selected_sets_awaiting_flag_and_prompts():
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={})

    await stt.handle_stt_tool_selected(update, context)

    assert context.user_data["awaiting_stt_voice"] is True
    message.reply_text.assert_awaited_once_with(stt._PROMPT_FOR_VOICE_MESSAGE)


# ------------------------------ محدودیت روزانه/کول‌داون + حجم فایل ------------------------------

@pytest.mark.asyncio
async def test_voice_rejected_when_stt_not_configured_before_download(monkeypatch):
    """پیش‌چک is_configured() باید *قبل* از دانلود ویس رد شود."""
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    monkeypatch.setattr(stt_service, "is_configured", lambda: False)

    await stt.handle_voice_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(messages.STT_UNAVAILABLE)


@pytest.mark.asyncio
async def test_voice_rejected_when_daily_stt_limit_reached(monkeypatch):
    """وقتی check_stt_limit رد کند، transcribe نباید اصلاً صدا زده شود."""
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    monkeypatch.setattr(
        stt_usage_repository, "check_stt_limit",
        AsyncMock(return_value=(False, "سقف روزانه‌ی ۵ دقیقه صدا پر شده.")),
    )
    transcribe_mock = AsyncMock(side_effect=AssertionError("transcribe نباید صدا زده شود"))
    monkeypatch.setattr(stt_service, "transcribe", transcribe_mock)

    await stt.handle_voice_message(update, context)

    transcribe_mock.assert_not_called()
    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with("⚠️ سقف روزانه‌ی ۵ دقیقه صدا پر شده.")


@pytest.mark.asyncio
async def test_check_stt_limit_called_with_voice_duration(monkeypatch):
    """سقف بر مبنای مدت واقعی ویس - duration باید از متادیتا خونده و
    به check_stt_limit پاس داده بشه."""
    update, message = _make_update_with_voice(duration=185)
    context = _make_context(user_data={"awaiting_stt_voice": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))
    check_mock = AsyncMock(return_value=(True, "OK"))
    monkeypatch.setattr(stt_usage_repository, "check_stt_limit", check_mock)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    )

    await stt.handle_voice_message(update, context)

    check_mock.assert_awaited_once_with(4242, 185)


@pytest.mark.asyncio
async def test_voice_provider_error_shows_distinct_message_and_skips_usage_increment(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(side_effect=stt_service.SttProviderError("all providers failed")),
    )
    report_issue_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_issue_mock)

    await stt.handle_voice_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(stt._PROVIDER_ERROR_MESSAGE)
    stt_usage_repository.record_attempt.assert_awaited_once_with(4242)
    stt_usage_repository.increment_stt_usage.assert_not_called()
    report_issue_mock.assert_awaited_once()
    args, kwargs = report_issue_mock.call_args
    assert "all providers failed" in args[1]
    assert kwargs["failure_feature"] == "stt"


@pytest.mark.asyncio
async def test_voice_increments_usage_with_duration_after_successful_processing(monkeypatch):
    update, message = _make_update_with_voice(duration=42)
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(return_value=stt_service.SttResult(text="متن یافت‌شده", provider="groq")),
    )

    await stt.handle_voice_message(update, context)

    stt_usage_repository.increment_stt_usage.assert_awaited_once_with(4242, 42)


@pytest.mark.asyncio
async def test_voice_increments_usage_even_when_genuinely_no_text_found(monkeypatch):
    update, message = _make_update_with_voice(duration=15)
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(return_value=stt_service.SttResult(text="", provider=None)),
    )

    await stt.handle_voice_message(update, context)

    stt_usage_repository.increment_stt_usage.assert_awaited_once_with(4242, 15)


@pytest.mark.asyncio
async def test_voice_logs_feature_usage_with_provider_detail(monkeypatch):
    from bme_bot.db import feature_usage_repository

    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(return_value=stt_service.SttResult(text="متن یافت‌شده", provider="elevenlabs")),
    )
    log_usage_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_usage_mock)

    await stt.handle_voice_message(update, context)

    log_usage_mock.assert_awaited_once_with(4242, "stt", detail="elevenlabs")


@pytest.mark.asyncio
async def test_voice_rejected_when_file_too_large(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    telegram_file = SimpleNamespace(
        download_as_bytearray=AsyncMock(return_value=bytearray(b"x" * (stt._MAX_AUDIO_BYTES + 1)))
    )
    context.bot.get_file = AsyncMock(return_value=telegram_file)
    transcribe_mock = AsyncMock(side_effect=AssertionError("transcribe نباید صدا زده شود"))
    monkeypatch.setattr(stt_service, "transcribe", transcribe_mock)

    await stt.handle_voice_message(update, context)

    transcribe_mock.assert_not_called()
    message.reply_text.assert_awaited_once()
    assert "بزرگ" in message.reply_text.await_args.args[0]


@pytest.mark.asyncio
async def test_tools_menu_now_includes_stt_button():
    from bme_bot.keyboards import reply_keyboards

    rendered = {btn.text for row in reply_keyboards.TOOLS_MENU_BUTTONS for btn in row}
    assert reply_keyboards.STT_TOOL_TEXT in rendered


# ------------------------------ معافیت کامل ادمین ------------------------------

@pytest.mark.asyncio
async def test_admin_skips_limit_check_entirely(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    check_mock = AsyncMock(side_effect=AssertionError("ادمین نباید اصلاً چک بشه"))
    monkeypatch.setattr(stt_usage_repository, "check_stt_limit", check_mock)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    )

    await stt.handle_voice_message(update, context)

    check_mock.assert_not_called()


@pytest.mark.asyncio
async def test_admin_does_not_consume_usage_quota(monkeypatch):
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    )

    await stt.handle_voice_message(update, context)

    stt_usage_repository.record_attempt.assert_not_called()
    stt_usage_repository.increment_stt_usage.assert_not_called()


@pytest.mark.asyncio
async def test_admin_still_blocked_by_service_unavailable(monkeypatch):
    """معافیت ادمین فقط شامل سهمیه‌ست، نه در دسترس‌بودن خودِ سرویس."""
    update, message = _make_update_with_voice()
    context = _make_context(user_data={"awaiting_stt_voice": True})
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    monkeypatch.setattr(stt_service, "is_configured", lambda: False)

    await stt.handle_voice_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(messages.STT_UNAVAILABLE)
