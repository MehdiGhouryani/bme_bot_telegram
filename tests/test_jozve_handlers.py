# tests/test_jozve_handlers.py
#
# تست هندلر «ویس استاد به جزوه»: چک متادیتا قبل از دانلود، تشخیص filename
# (ویس‌نوت در برابر فایل آپلودی)، مسیر خطای STT/ساختاردهی جدا از هم، و
# تحویل نهایی به‌شکل فایل .md. ساختار از test_stt_handlers.py الگو گرفته
# شده، با تفاوت‌های لازم برای پایپ‌لاین دومرحله‌ای (STT + AI).

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.db import jozve_usage_repository  # noqa: E402
from bme_bot.handlers import jozve  # noqa: E402
from bme_bot.services import ai_service, stt_service  # noqa: E402
from bme_bot.utils import admin as admin_utils  # noqa: E402
from bme_bot.utils import error_reporting, messages  # noqa: E402


@pytest.fixture(autouse=True)
def _allow_by_default(monkeypatch):
    monkeypatch.setattr(stt_service, "is_configured", lambda: True)
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: False)
    monkeypatch.setattr(jozve_usage_repository, "check_jozve_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(jozve_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(jozve_usage_repository, "increment_jozve_usage", AsyncMock())


def _make_voice_update(duration=600, file_size=5_000_000):
    voice = SimpleNamespace(file_id="voice-id", duration=duration, file_size=file_size)
    message = SimpleNamespace(voice=voice, audio=None, reply_text=AsyncMock())
    update = SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=4242),
        effective_chat=SimpleNamespace(id=777),
    )
    return update, message


def _make_audio_update(file_name="lecture.mp3", mime_type="audio/mpeg", duration=900, file_size=8_000_000):
    audio = SimpleNamespace(
        file_id="audio-id", duration=duration, file_size=file_size,
        file_name=file_name, mime_type=mime_type,
    )
    message = SimpleNamespace(voice=None, audio=audio, reply_text=AsyncMock())
    update = SimpleNamespace(
        message=message,
        effective_user=SimpleNamespace(id=4242),
        effective_chat=SimpleNamespace(id=777),
    )
    return update, message


def _make_context(user_data=None):
    telegram_file = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(b"fake-audio-bytes")))
    bot = SimpleNamespace(
        get_file=AsyncMock(return_value=telegram_file),
        send_document=AsyncMock(),
        do_api_request=AsyncMock(),  # برای send_rich_message — پیام غنی، اضافه بر فایل
    )
    return SimpleNamespace(user_data=user_data if user_data is not None else {}, bot=bot)


# ------------------------------- تشخیص filename -------------------------------

def test_determine_filename_voice_is_always_ogg():
    message = SimpleNamespace(voice=SimpleNamespace(), audio=None)
    assert jozve._determine_filename(message) == "voice.ogg"


def test_determine_filename_uses_real_file_name_when_present():
    message = SimpleNamespace(voice=None, audio=SimpleNamespace(file_name="my_lecture.wav", mime_type="audio/wav"))
    assert jozve._determine_filename(message) == "my_lecture.wav"


def test_determine_filename_falls_back_to_mimetype_when_no_file_name():
    message = SimpleNamespace(voice=None, audio=SimpleNamespace(file_name=None, mime_type="audio/mp4"))
    assert jozve._determine_filename(message) == "audio.m4a"


def test_determine_filename_defaults_to_mp3_for_unknown_mimetype():
    message = SimpleNamespace(voice=None, audio=SimpleNamespace(file_name=None, mime_type="application/octet-stream"))
    assert jozve._determine_filename(message) == "audio.mp3"


# ------------------------------- پرچم + چک متادیتا قبل از دانلود -------------------------------

@pytest.mark.asyncio
async def test_ignored_when_not_awaiting_jozve_audio():
    update, message = _make_voice_update()
    context = _make_context(user_data={})

    await jozve.handle_jozve_audio_message(update, context)

    message.reply_text.assert_not_called()
    context.bot.get_file.assert_not_called()


@pytest.mark.asyncio
async def test_rejected_when_duration_exceeds_20_minutes_before_download():
    update, message = _make_voice_update(duration=21 * 60)
    context = _make_context(user_data={"awaiting_jozve_audio": True})

    await jozve.handle_jozve_audio_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(jozve._TOO_LONG_MESSAGE)


@pytest.mark.asyncio
async def test_rejected_when_file_size_metadata_exceeds_cap_before_download():
    update, message = _make_voice_update(duration=600, file_size=25 * 1024 * 1024)
    context = _make_context(user_data={"awaiting_jozve_audio": True})

    await jozve.handle_jozve_audio_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(jozve._TOO_LARGE_MESSAGE)


@pytest.mark.asyncio
async def test_rejected_when_stt_not_configured_before_download(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    monkeypatch.setattr(stt_service, "is_configured", lambda: False)

    await jozve.handle_jozve_audio_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with(messages.STT_UNAVAILABLE)


@pytest.mark.asyncio
async def test_rejected_when_daily_limit_reached(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    monkeypatch.setattr(
        jozve_usage_repository, "check_jozve_limit",
        AsyncMock(return_value=(False, "شما از تمام 3 جزوه‌سازی روزانه‌ی خود استفاده کرده‌اید.")),
    )

    await jozve.handle_jozve_audio_message(update, context)

    context.bot.get_file.assert_not_called()
    message.reply_text.assert_awaited_once_with("⚠️ شما از تمام 3 جزوه‌سازی روزانه‌ی خود استفاده کرده‌اید.")


@pytest.mark.asyncio
async def test_clears_awaiting_flag_even_when_rejected():
    update, message = _make_voice_update(duration=99 * 60)
    context = _make_context(user_data={"awaiting_jozve_audio": True})

    await jozve.handle_jozve_audio_message(update, context)

    assert "awaiting_jozve_audio" not in context.user_data


# ------------------------------- مسیر موفق کامل -------------------------------

@pytest.mark.asyncio
async def test_full_success_path_sends_md_document(monkeypatch):
    update, message = _make_audio_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(return_value=stt_service.SttResult(text="متن پیاده‌شده‌ی کلاس", provider="groq")),
    )
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("## جزوه\n- **نکته** - توضیح", "gemini/gemini-2.5-flash")))

    await jozve.handle_jozve_audio_message(update, context)

    context.bot.send_document.assert_awaited_once()
    _, kwargs = context.bot.send_document.call_args
    assert kwargs["document"].filename == "jozve.md"
    processing_msg.delete.assert_awaited_once()
    # پیام غنی (Bot API 10.1) هم علاوه بر فایل باید ارسال بشه — برای
    # خوندن فوری جزوه داخل چت بدون دانلود.
    context.bot.do_api_request.assert_awaited_once_with(
        "sendRichMessage",
        {"chat_id": 777, "rich_message": {"markdown": "## جزوه\n- **نکته** - توضیح"}},
    )


@pytest.mark.asyncio
async def test_full_success_path_still_sends_file_if_rich_message_fails(monkeypatch):
    """پیام غنی کاملاً افزوده است — شکستش نباید فایل (که همیشه کار
    می‌کرده) رو تحت تاثیر قرار بده."""
    update, message = _make_audio_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    context.bot.do_api_request = AsyncMock(side_effect=Exception("rich message rejected"))
    processing_msg = SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe",
        AsyncMock(return_value=stt_service.SttResult(text="متن پیاده‌شده‌ی کلاس", provider="groq")),
    )
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("## جزوه", "gemini/gemini-2.5-flash")))

    await jozve.handle_jozve_audio_message(update, context)

    context.bot.send_document.assert_awaited_once()
    jozve_usage_repository.increment_jozve_usage.assert_awaited_once_with(4242)


@pytest.mark.asyncio
async def test_transcribe_called_with_real_filename_for_uploaded_file(monkeypatch):
    update, message = _make_audio_update(file_name="physiology_lecture.wav")
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    transcribe_mock = AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    monkeypatch.setattr(stt_service, "transcribe", transcribe_mock)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("جزوه", "gemini/gemini-2.5-flash")))

    await jozve.handle_jozve_audio_message(update, context)

    transcribe_mock.assert_awaited_once_with(b"fake-audio-bytes", filename="physiology_lecture.wav")


@pytest.mark.asyncio
async def test_voice_message_transcribed_with_default_ogg_filename(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    transcribe_mock = AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    monkeypatch.setattr(stt_service, "transcribe", transcribe_mock)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("جزوه", "gemini/gemini-2.5-flash")))

    await jozve.handle_jozve_audio_message(update, context)

    transcribe_mock.assert_awaited_once_with(b"fake-audio-bytes", filename="voice.ogg")


# ------------------------------- مسیرهای خطا: STT -------------------------------

@pytest.mark.asyncio
async def test_stt_service_unavailable_reports_with_jozve_stt_label(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(side_effect=stt_service.SttServiceUnavailable("no keys"))
    )
    report_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_mock)

    await jozve.handle_jozve_audio_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(messages.STT_UNAVAILABLE)
    _, kwargs = report_mock.call_args
    assert kwargs["context_label"] == "jozve.stt"
    assert kwargs["failure_feature"] == "jozve"
    context.bot.send_document.assert_not_called()


@pytest.mark.asyncio
async def test_stt_provider_error_does_not_reach_structuring(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock()))
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(side_effect=stt_service.SttProviderError("chain failed"))
    )
    ask_mock = AsyncMock(side_effect=AssertionError("نباید به ساختاردهی برسه"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)
    monkeypatch.setattr(error_reporting, "report_service_issue", AsyncMock())

    await jozve.handle_jozve_audio_message(update, context)

    ask_mock.assert_not_called()


@pytest.mark.asyncio
async def test_empty_stt_result_increments_usage_but_skips_structuring(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="", provider=None))
    )
    ask_mock = AsyncMock(side_effect=AssertionError("نباید به ساختاردهی برسه"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await jozve.handle_jozve_audio_message(update, context)

    ask_mock.assert_not_called()
    processing_msg.edit_text.assert_awaited_once_with(jozve._NO_SPEECH_MESSAGE)
    jozve_usage_repository.increment_jozve_usage.assert_awaited_once_with(4242)


# ------------------------------- مسیرهای خطا: ساختاردهی -------------------------------

@pytest.mark.asyncio
async def test_structuring_service_unavailable_reports_with_jozve_structuring_label(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    )
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIServiceUnavailable("no key")))
    report_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_mock)

    await jozve.handle_jozve_audio_message(update, context)

    processing_msg.edit_text.assert_awaited_once_with(jozve._AI_UNAVAILABLE_MESSAGE)
    _, kwargs = report_mock.call_args
    assert kwargs["context_label"] == "jozve.structuring"
    context.bot.send_document.assert_not_called()


@pytest.mark.asyncio
async def test_structuring_empty_response_still_counts_usage(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    processing_msg = SimpleNamespace(edit_text=AsyncMock())
    message.reply_text = AsyncMock(return_value=processing_msg)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    )
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIResponseEmpty(blocked=False)))

    await jozve.handle_jozve_audio_message(update, context)

    jozve_usage_repository.increment_jozve_usage.assert_awaited_once_with(4242)
    context.bot.send_document.assert_not_called()


@pytest.mark.asyncio
async def test_logs_feature_usage_with_structuring_model_detail(monkeypatch):
    from bme_bot.db import feature_usage_repository

    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    )
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("جزوه", "groq/openai/gpt-oss-120b")))
    log_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_mock)

    await jozve.handle_jozve_audio_message(update, context)

    log_mock.assert_awaited_once_with(4242, "jozve", detail="groq/openai/gpt-oss-120b")


def test_tools_menu_includes_jozve_button():
    from bme_bot.keyboards import reply_keyboards

    rendered = {btn.text for row in reply_keyboards.TOOLS_MENU_BUTTONS for btn in row}
    assert reply_keyboards.JOZVE_TOOL_TEXT in rendered


# --- معافیت کامل ادمین ---

@pytest.mark.asyncio
async def test_admin_skips_limit_check_entirely(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    check_mock = AsyncMock(side_effect=AssertionError("ادمین نباید اصلاً چک بشه"))
    monkeypatch.setattr(jozve_usage_repository, "check_jozve_limit", check_mock)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    )
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("جزوه", "gemini/gemini-2.5-flash")))

    await jozve.handle_jozve_audio_message(update, context)

    check_mock.assert_not_called()


@pytest.mark.asyncio
async def test_admin_does_not_consume_usage_quota(monkeypatch):
    update, message = _make_voice_update()
    context = _make_context(user_data={"awaiting_jozve_audio": True})
    message.reply_text = AsyncMock(return_value=SimpleNamespace(edit_text=AsyncMock(), delete=AsyncMock()))
    monkeypatch.setattr(admin_utils, "is_admin", lambda user_id: True)
    monkeypatch.setattr(
        stt_service, "transcribe", AsyncMock(return_value=stt_service.SttResult(text="متن", provider="groq"))
    )
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("جزوه", "gemini/gemini-2.5-flash")))

    await jozve.handle_jozve_audio_message(update, context)

    jozve_usage_repository.record_attempt.assert_not_called()
    jozve_usage_repository.increment_jozve_usage.assert_not_called()
