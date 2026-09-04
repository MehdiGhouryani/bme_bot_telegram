# tests/test_stt_service.py
#
# تست‌های زنجیره‌ی STT. هیچ‌کدام واقعاً به شبکه/ElevenLabs/Groq/... وصل
# نمی‌شوند — httpx.AsyncClient mock می‌شود (همان الگوی test_ocr_service.py)،
# با یک تفاوت: چون AssemblyAI سه فراخوانی پشت‌سرهم (آپلود→ساخت→poll) دارد،
# اینجا یک فیک صف‌محور (queue) استفاده شده به‌جای یک پاسخ ثابت. تایرهایی که
# به ffmpeg/SpeechRecognition نیاز دارند (azure، google_unofficial) با
# monkeypatch مستقیم روی همان توابع کمکی تست می‌شوند، نه با اجرای واقعی
# ffmpeg/شبکه.

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.services import stt_service  # noqa: E402


class _FakeResponse:
    def __init__(self, json_data=None, status_code=200, text=None, reason_phrase="Error"):
        self._json_data = json_data
        self.status_code = status_code
        self.text = text if text is not None else (json.dumps(json_data) if json_data is not None else "")
        self.reason_phrase = reason_phrase
        self.request = None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    """فیک صف‌محور: هر post/get آیتم بعدی صف را برمی‌گرداند (یا exception
    صف را raise می‌کند). برای زنجیره‌های چندمرحله‌ای مثل AssemblyAI لازم است."""

    _queue: list = []
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def _consume(self, method, url, **kwargs):
        type(self).calls.append({"method": method, "url": url, **kwargs})
        if not type(self)._queue:
            raise AssertionError(f"صف پاسخ فیک خالی شد (فراخوانی {method} {url})")
        item = type(self)._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def post(self, url, **kwargs):
        return await self._consume("post", url, **kwargs)

    async def get(self, url, **kwargs):
        return await self._consume("get", url, **kwargs)


@pytest.fixture(autouse=True)
def _reset_fake_client():
    _FakeAsyncClient._queue = []
    _FakeAsyncClient.calls = []
    yield


@pytest.fixture(autouse=True)
def _default_no_keys_configured(monkeypatch):
    """پیش‌فرض هر تست: هیچ کلیدی تنظیم نشده — هر تست خودش کلید لازم را ست می‌کند."""
    for key in (
        "ELEVENLABS_API_KEY", "GROQ_API_KEY", "DEEPGRAM_API_KEY", "ASSEMBLYAI_API_KEY",
        "AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION", "GOOGLE_STT_API_KEY", "WIT_AI_TOKEN",
    ):
        monkeypatch.setattr(config, key, None)
    monkeypatch.setattr(
        config, "STT_PROVIDER_ORDER",
        ["elevenlabs", "groq", "deepgram", "assemblyai", "azure", "google", "wit", "google_unofficial"],
    )
    import httpx
    from types import SimpleNamespace
    monkeypatch.setattr(stt_service, "httpx", SimpleNamespace(
        AsyncClient=_FakeAsyncClient,
        Timeout=httpx.Timeout,
        # کلاس‌های exception واقعی httpx — retry.is_retryable و
        # stt_service._try_google با isinstance/response.status_code روی
        # اینا کار می‌کنن.
        HTTPStatusError=httpx.HTTPStatusError,
        TimeoutException=httpx.TimeoutException,
        NetworkError=httpx.NetworkError,
    ))


def _q(*items):
    _FakeAsyncClient._queue = list(items)


# ------------------------------- orchestrator -------------------------------

@pytest.mark.asyncio
async def test_transcribe_raises_unavailable_when_nothing_configured(monkeypatch):
    """google_unofficial بدون کلید کار می‌کند (فقط به نصب بودن پکیج نیاز
    دارد) - برای تست واقعی «هیچی پیکربندی نشده» باید آن را از ترتیب حذف کرد،
    وگرنه همیشه به‌عنوان یک تایر «موجود» شمرده می‌شود."""
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs", "groq", "deepgram"])
    with pytest.raises(stt_service.SttServiceUnavailable):
        await stt_service.transcribe(b"fake-audio-bytes")


@pytest.mark.asyncio
async def test_transcribe_returns_elevenlabs_result_when_configured(monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs"])
    _q(_FakeResponse({"text": "سلام دنیا"}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == "سلام دنیا"
    assert result.provider == "elevenlabs"


@pytest.mark.asyncio
async def test_transcribe_skips_unconfigured_and_falls_through_to_groq(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs", "groq"])
    _q(_FakeResponse({"text": "متن از گروک"}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == "متن از گروک"
    assert result.provider == "groq"
    assert len(_FakeAsyncClient.calls) == 1  # elevenlabs اصلاً فراخوانی نشد


@pytest.mark.asyncio
async def test_transcribe_falls_through_to_next_provider_on_empty_result(monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs", "groq"])
    _q(_FakeResponse({"text": ""}), _FakeResponse({"text": "متن از گروک"}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == "متن از گروک"
    assert result.provider == "groq"


@pytest.mark.asyncio
async def test_transcribe_falls_through_to_next_provider_on_error(monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs", "groq"])
    # پیام عمداً بدون کلیدواژه‌ی retryable (utils/retry.is_retryable) انتخاب
    # شده - تا فقط یک تلاش مصرف شود، نه دو (retries=1 هر تایر).
    _q(RuntimeError("invalid credentials"), _FakeResponse({"text": "متن از گروک"}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == "متن از گروک"
    assert result.provider == "groq"


@pytest.mark.asyncio
async def test_transcribe_returns_empty_result_when_all_configured_providers_find_nothing(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["groq"])
    _q(_FakeResponse({"text": ""}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == ""
    assert result.provider is None


@pytest.mark.asyncio
async def test_transcribe_raises_provider_error_when_only_configured_layer_fails(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["groq"])
    _q(RuntimeError("invalid credentials"))

    with pytest.raises(stt_service.SttProviderError):
        await stt_service.transcribe(b"fake-audio-bytes")


@pytest.mark.asyncio
async def test_transcribe_provider_error_takes_precedence_even_if_later_layer_also_empty(monkeypatch):
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs", "groq"])
    _q(RuntimeError("elevenlabs boom"), _FakeResponse({"text": ""}))

    with pytest.raises(stt_service.SttProviderError):
        await stt_service.transcribe(b"fake-audio-bytes")


@pytest.mark.asyncio
async def test_transcribe_respects_custom_provider_order(monkeypatch):
    """اگر ترتیب از .env بازنویسی شود (مثلاً groq اول)، همان ترتیب رعایت شود."""
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["groq", "elevenlabs"])
    _q(_FakeResponse({"text": "اول گروک"}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.provider == "groq"
    assert _FakeAsyncClient.calls[0]["url"] == "https://api.groq.com/openai/v1/audio/transcriptions"


@pytest.mark.asyncio
async def test_unknown_provider_name_in_order_is_skipped_without_crashing(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["not_a_real_provider", "groq"])
    _q(_FakeResponse({"text": "سلام"}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.provider == "groq"


def test_is_configured_true_when_any_single_key_present(monkeypatch):
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs", "groq"])  # بدون google_unofficial
    assert stt_service.is_configured() is False  # هیچ کلیدی نیست و تایر بی‌کلید هم در ترتیب نیست
    monkeypatch.setattr(config, "WIT_AI_TOKEN", "fake-token")
    assert stt_service.is_configured() is True


def test_is_configured_true_via_google_unofficial_even_with_zero_keys(monkeypatch):
    """رفع باگ بازبینی: google_unofficial به هیچ کلیدی نیاز ندارد (فقط نصب
    بودن پکیج speech_recognition)، پس باید همان چیزی را بسنجد که transcribe()
    واقعاً امتحان می‌کند - وگرنه در دقیقاً وضعیت فعلی کاربر (هیچ کلیدی هنوز
    ست نشده) هندلر به‌اشتباه «سرویس در دسترس نیست» نشان می‌دهد، در حالی که
    تایر رایگان آخر واقعاً کار می‌کرد."""
    monkeypatch.setattr(
        config, "STT_PROVIDER_ORDER",
        ["elevenlabs", "groq", "deepgram", "assemblyai", "azure", "google", "wit", "google_unofficial"],
    )
    assert stt_service.is_configured() is True


def test_is_configured_false_when_google_unofficial_not_in_order_and_no_keys(monkeypatch):
    """اگر ادمین عمداً google_unofficial (تایر غیررسمی/ریسک‌دار) را از
    ترتیب حذف کند، is_configured() نباید صرفاً به‌خاطر نصب‌بودن پکیج True
    برگرداند - باید واقعاً منعکس‌کننده‌ی چیزی باشد که در ترتیب فعلی هست."""
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs", "groq"])
    assert stt_service.is_configured() is False


def test_is_configured_requires_both_azure_key_and_region(monkeypatch):
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["azure"])  # بدون google_unofficial
    monkeypatch.setattr(config, "AZURE_SPEECH_KEY", "fake-key")
    assert stt_service.is_configured() is False  # فقط کلید، بدون region کافی نیست
    monkeypatch.setattr(config, "AZURE_SPEECH_REGION", "westeurope")
    assert stt_service.is_configured() is True


# ------------------------------ per-provider جزئیات ------------------------------

@pytest.mark.asyncio
async def test_elevenlabs_sends_model_id_without_language_code(monkeypatch):
    """Scribe خودش زبان را تشخیص می‌دهد - language_code
    عمداً نباید ارسال شود."""
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["elevenlabs"])
    _q(_FakeResponse({"text": "ok"}))

    await stt_service.transcribe(b"fake-audio-bytes")

    call = _FakeAsyncClient.calls[0]
    assert call["headers"]["xi-api-key"] == "fake-key"
    assert call["data"]["model_id"] == "scribe_v2"
    assert "language_code" not in call["data"]


@pytest.mark.asyncio
async def test_deepgram_uses_monolingual_fa_not_multi(monkeypatch):
    """language=multi از فارسی پشتیبانی نمی‌کند."""
    monkeypatch.setattr(config, "DEEPGRAM_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["deepgram"])
    _q(_FakeResponse({
        "results": {"channels": [{"alternatives": [{"transcript": "متن دیپگرم"}]}]}
    }))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == "متن دیپگرم"
    call = _FakeAsyncClient.calls[0]
    assert call["params"]["language"] == "fa"
    assert call["params"]["model"] == "nova-3"


@pytest.mark.asyncio
async def test_google_does_not_hardcode_sample_rate_for_ogg_opus(monkeypatch):
    """رفع یافته‌ی بازبینی: sampleRateHertz دستی نباید ارسال شود، تا با نرخ
    واقعی هدر OGG کاربر تداخل نکند."""
    monkeypatch.setattr(config, "GOOGLE_STT_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["google"])
    _q(_FakeResponse({"results": [{"alternatives": [{"transcript": "متن گوگل"}]}]}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == "متن گوگل"
    sent_payload = _FakeAsyncClient.calls[0]["json"]
    assert sent_payload["config"]["encoding"] == "OGG_OPUS"
    assert "sampleRateHertz" not in sent_payload["config"]
    assert sent_payload["config"]["languageCode"] == "fa-IR"


@pytest.mark.asyncio
async def test_google_stt_error_message_never_contains_the_api_key(monkeypatch):
    """رگرسیون: مثل تست مشابه در test_ocr_service.py — Google STT هم کلید رو
    به‌عنوان query param می‌فرسته، پس پیام پیش‌فرض httpx (URL کامل) کلید رو
    لو می‌داد. یه لاگ production واقعی همین الگو رو برای Google Vision
    تایید کرد؛ این تست مطمئن می‌شه همون رفع برای Google STT هم اعمال شده."""
    secret_key = "AIzaSuperSecretGoogleSttKey456"
    monkeypatch.setattr(config, "GOOGLE_STT_API_KEY", secret_key)
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["google"])
    _q(_FakeResponse({}, status_code=401, reason_phrase="Unauthorized"))

    with pytest.raises(stt_service.SttProviderError) as exc_info:
        await stt_service.transcribe(b"fake-audio-bytes", "voice.ogg")

    full_text = f"{exc_info.value}\n{exc_info.value.__cause__}"
    assert secret_key not in full_text
    assert "401" in str(exc_info.value.__cause__)


@pytest.mark.asyncio
async def test_google_missing_alternatives_is_empty_not_error(monkeypatch):
    """صدای خیلی کوتاه/بی‌صدا → پاسخ بدون results یعنی «واقعاً متنی نبود»،
    نه یک خطای provider."""
    monkeypatch.setattr(config, "GOOGLE_STT_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["google"])
    _q(_FakeResponse({}))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == ""
    assert result.provider is None


# ------------------------- filename/mimetype passthrough -------------------------

@pytest.mark.asyncio
async def test_transcribe_default_filename_preserves_existing_stt_tool_behavior(monkeypatch):
    """فیچر STT فعلی filename پاس نمی‌ده - باید دقیقاً مثل قبل voice.ogg/audio-ogg بمونه."""
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["groq"])
    _q(_FakeResponse({"text": "سلام"}))

    await stt_service.transcribe(b"fake-audio-bytes")  # بدون آرگومان filename

    call = _FakeAsyncClient.calls[0]
    assert call["files"]["file"] == ("voice.ogg", b"fake-audio-bytes", "audio/ogg")


@pytest.mark.asyncio
async def test_transcribe_passes_real_filename_and_mimetype_for_uploaded_mp3(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["groq"])
    _q(_FakeResponse({"text": "سلام"}))

    await stt_service.transcribe(b"fake-mp3-bytes", filename="lecture.mp3")

    call = _FakeAsyncClient.calls[0]
    assert call["files"]["file"] == ("lecture.mp3", b"fake-mp3-bytes", "audio/mpeg")


@pytest.mark.asyncio
async def test_deepgram_content_type_follows_real_filename(monkeypatch):
    monkeypatch.setattr(config, "DEEPGRAM_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["deepgram"])
    _q(_FakeResponse({
        "results": {"channels": [{"alternatives": [{"transcript": "متن"}]}]}
    }))

    await stt_service.transcribe(b"fake-wav-bytes", filename="lecture.wav")

    assert _FakeAsyncClient.calls[0]["headers"]["Content-Type"] == "audio/wav"


@pytest.mark.asyncio
async def test_google_official_self_skips_for_non_ogg_filename(monkeypatch):
    """encoding: OGG_OPUS تو این تایر هاردکده - برای فایل mp3 آپلودی، این
    تایر باید خودش رد بشه (نه این‌که encoding غلط بفرسته که حتماً fail می‌شه)."""
    monkeypatch.setattr(config, "GOOGLE_STT_API_KEY", "fake-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["google", "groq"])
    _q(_FakeResponse({"text": "متن از گروک"}))  # فقط یکی - google اصلاً نباید فراخوانی بشه

    result = await stt_service.transcribe(b"fake-mp3-bytes", filename="lecture.mp3")

    assert result.provider == "groq"
    assert len(_FakeAsyncClient.calls) == 1


@pytest.mark.asyncio
async def test_google_official_still_works_for_real_ogg_filename(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_STT_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["google"])
    _q(_FakeResponse({"results": [{"alternatives": [{"transcript": "متن گوگل"}]}]}))

    result = await stt_service.transcribe(b"fake-audio-bytes", filename="voice.ogg")

    assert result.text == "متن گوگل"


@pytest.mark.asyncio
async def test_wit_parses_last_valid_json_line_from_streaming_response(monkeypatch):
    monkeypatch.setattr(config, "WIT_AI_TOKEN", "fake-token")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["wit"])
    # wit.ai همیشه اول به WAV تبدیل می‌شود (سازگاری Content-Type) - ffmpeg
    # واقعی صدا زده نمی‌شود، مستقیم mock می‌شود.
    monkeypatch.setattr(stt_service, "_ogg_to_wav_bytes", AsyncMock(return_value=b"FAKE-WAV-BYTES"))
    streaming_body = '{"text": "نیمه"}\n{"text": "متن کامل"}'
    _q(_FakeResponse(text=streaming_body))

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == "متن کامل"
    assert _FakeAsyncClient.calls[0]["content"] == b"FAKE-WAV-BYTES"
    assert _FakeAsyncClient.calls[0]["headers"]["Content-Type"] == "audio/wav"


@pytest.mark.asyncio
async def test_assemblyai_full_three_step_flow_with_polling(monkeypatch):
    monkeypatch.setattr(config, "ASSEMBLYAI_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["assemblyai"])
    monkeypatch.setattr(stt_service.asyncio, "sleep", AsyncMock())  # تست را کند نکند

    _q(
        _FakeResponse({"upload_url": "https://cdn.assemblyai.com/upload/abc"}),  # آپلود
        _FakeResponse({"id": "transcript-123"}),  # ساخت
        _FakeResponse({"status": "processing"}),  # poll ۱
        _FakeResponse({"status": "completed", "text": "متن نهایی اسمبلی"}),  # poll ۲
    )

    result = await stt_service.transcribe(b"fake-audio-bytes")

    assert result.text == "متن نهایی اسمبلی"
    assert result.provider == "assemblyai"
    assert _FakeAsyncClient.calls[0]["url"] == "https://api.assemblyai.com/v2/upload"
    assert _FakeAsyncClient.calls[1]["json"]["audio_url"] == "https://cdn.assemblyai.com/upload/abc"
    assert _FakeAsyncClient.calls[1]["json"]["language_code"] == "fa"


@pytest.mark.asyncio
async def test_assemblyai_error_status_raises_provider_error(monkeypatch):
    monkeypatch.setattr(config, "ASSEMBLYAI_API_KEY", "fake-key")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["assemblyai"])
    monkeypatch.setattr(stt_service.asyncio, "sleep", AsyncMock())

    _q(
        _FakeResponse({"upload_url": "https://cdn.assemblyai.com/upload/abc"}),
        _FakeResponse({"id": "transcript-123"}),
        _FakeResponse({"status": "error", "error": "invalid audio format"}),
    )

    with pytest.raises(stt_service.SttProviderError):
        await stt_service.transcribe(b"fake-audio-bytes")


@pytest.mark.asyncio
async def test_azure_converts_ogg_to_wav_before_sending(monkeypatch):
    """ffmpeg واقعاً اجرا نمی‌شود - _ogg_to_wav_bytes مستقیم mock می‌شود."""
    monkeypatch.setattr(config, "AZURE_SPEECH_KEY", "fake-key")
    monkeypatch.setattr(config, "AZURE_SPEECH_REGION", "westeurope")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["azure"])
    monkeypatch.setattr(stt_service, "_ogg_to_wav_bytes", AsyncMock(return_value=b"FAKE-WAV-BYTES"))
    _q(_FakeResponse({"RecognitionStatus": "Success", "DisplayText": "متن آژور"}))

    result = await stt_service.transcribe(b"fake-ogg-bytes")

    assert result.text == "متن آژور"
    call = _FakeAsyncClient.calls[0]
    assert call["content"] == b"FAKE-WAV-BYTES"
    assert call["url"] == "https://westeurope.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    assert call["params"]["language"] == "fa-IR"


@pytest.mark.asyncio
async def test_azure_non_success_recognition_status_raises_provider_error(monkeypatch):
    monkeypatch.setattr(config, "AZURE_SPEECH_KEY", "fake-key")
    monkeypatch.setattr(config, "AZURE_SPEECH_REGION", "westeurope")
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["azure"])
    monkeypatch.setattr(stt_service, "_ogg_to_wav_bytes", AsyncMock(return_value=b"FAKE-WAV-BYTES"))
    _q(_FakeResponse({"RecognitionStatus": "NoMatch"}))

    with pytest.raises(stt_service.SttProviderError):
        await stt_service.transcribe(b"fake-ogg-bytes")


@pytest.mark.asyncio
async def test_google_unofficial_runs_blocking_call_in_thread(monkeypatch):
    """هیچ httpx‌ای درگیر نیست - این تایر از asyncio.to_thread دور یک تابع
    sync استفاده می‌کند؛ اینجا هم تبدیل ogg->wav و هم خودِ تشخیص mock می‌شوند."""
    monkeypatch.setattr(config, "STT_PROVIDER_ORDER", ["google_unofficial"])
    monkeypatch.setattr(stt_service, "_ogg_to_wav_bytes", AsyncMock(return_value=b"FAKE-WAV-BYTES"))
    monkeypatch.setattr(
        stt_service, "_blocking_recognize_google_unofficial",
        lambda wav_bytes: "متن گوگل غیررسمی" if wav_bytes == b"FAKE-WAV-BYTES" else "",
    )

    result = await stt_service.transcribe(b"fake-ogg-bytes")

    assert result.text == "متن گوگل غیررسمی"
    assert result.provider == "google_unofficial"
    assert _FakeAsyncClient.calls == []  # هیچ تماس شبکه‌ی httpx‌ای نباید ثبت شده باشد


@pytest.mark.asyncio
async def test_ogg_to_wav_uses_async_subprocess_not_blocking_subprocess_run(monkeypatch):
    """این تست تایید می‌کند asyncio.create_subprocess_exec واقعاً استفاده
    می‌شود، نه subprocess.run بلاک‌کننده (که با یک TimeoutExpired ناگرفته
    می‌تواند کل event loop را مسدود کند)."""
    import asyncio as real_asyncio

    class _FakeProc:
        returncode = 0

        async def communicate(self, input=None):
            assert input == b"fake-ogg-bytes"
            return b"FAKE-WAV-OUTPUT", b""

        def kill(self):
            pass

        async def wait(self):
            pass

    async def _fake_create_subprocess_exec(*args, **kwargs):
        assert args[0] == "ffmpeg"
        return _FakeProc()

    monkeypatch.setattr(real_asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    wav_bytes = await stt_service._ogg_to_wav_bytes(b"fake-ogg-bytes")

    assert wav_bytes == b"FAKE-WAV-OUTPUT"


@pytest.mark.asyncio
async def test_ogg_to_wav_raises_stt_provider_error_on_ffmpeg_failure(monkeypatch):
    import asyncio as real_asyncio

    class _FakeFailingProc:
        returncode = 1

        async def communicate(self, input=None):
            return b"", b"invalid data found"

        def kill(self):
            pass

        async def wait(self):
            pass

    async def _fake_create_subprocess_exec(*args, **kwargs):
        return _FakeFailingProc()

    monkeypatch.setattr(real_asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    with pytest.raises(stt_service.SttProviderError):
        await stt_service._ogg_to_wav_bytes(b"fake-ogg-bytes")


@pytest.mark.asyncio
async def test_ogg_to_wav_missing_ffmpeg_raises_stt_provider_error(monkeypatch):
    import asyncio as real_asyncio

    async def _raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(real_asyncio, "create_subprocess_exec", _raise_file_not_found)

    with pytest.raises(stt_service.SttProviderError):
        await stt_service._ogg_to_wav_bytes(b"fake-ogg-bytes")


# --- test_all_providers (دکمه‌ی «🩺 تست سرویس‌ها الان» تو پنل ادمین) ---
#
# _PROVIDER_FUNCS مستقیم monkeypatch می‌شه (نه شبیه‌سازی هر ۸ پروتکل واقعی)
# — چون google_unofficial فقط با نصب‌بودن speech_recognition «پیکربندی‌شده»
# محسوب می‌شه (نه یه کلید API)، و اون پکیج تو همین محیط تست واقعاً نصبه؛
# بدون این mock، تست واقعاً سعی می‌کرد ffmpeg اجرا کنه و به API غیررسمی
# گوگل وصل بشه. هدف این تست منطق orchestration خودِ test_all_providers هست
# (همه رو جدا صدا بزنه، یکی شکست بخوره بقیه متوقف نشن) نه قرارداد HTTP هر
# provider (که جای دیگه‌ی همین فایل جدا تست شده).

@pytest.mark.asyncio
async def test_test_all_providers_checks_every_provider_independently(monkeypatch):
    async def fake_ok(audio_bytes, filename):
        return "متن تست"

    async def fake_not_configured(audio_bytes, filename):
        raise stt_service.SttProviderNotConfigured("x")

    async def fake_failure(audio_bytes, filename):
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(stt_service, "_PROVIDER_FUNCS", {
        "elevenlabs": fake_ok,
        "azure": fake_not_configured,
        "groq": fake_failure,
    })

    results = await stt_service.test_all_providers()

    assert results == [
        ("elevenlabs", True, "OK"),
        ("azure", None, "پیکربندی نشده"),
        ("groq", False, "401 Unauthorized"),
    ]


@pytest.mark.asyncio
async def test_make_test_wav_bytes_is_a_valid_wav_file():
    """تست ساز فایل صوتی خودش هم باید یه WAV واقعاً معتبر بسازه — وگرنه
    تست بالا معنی نداره."""
    import io
    import wave

    wav_bytes = stt_service._make_test_wav_bytes()

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 16000
        assert w.getnframes() > 0
