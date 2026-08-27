# tests/test_ocr_service.py
#
# تست‌های زنجیره‌ی OCR. هیچ‌کدام واقعاً به شبکه/Google/Azure/Groq وصل
# نمی‌شوند — httpx.AsyncClient و litellm.acompletion هر دو mock می‌شوند،
# دقیقاً همان الگوی tests/test_ai_service.py برای litellm.
#
# تست‌های OcrProviderError (تمایز خطای واقعی provider از «واقعاً متنی
# نبود») و is_configured() در انتهای فایل هستند.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.services import ocr_service  # noqa: E402


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    """جایگزین httpx.AsyncClient برای تست — یک پاسخ از پیش‌تعیین‌شده برمی‌گرداند
    یا یک استثنا raise می‌کند، بدون هیچ تماس شبکه‌ی واقعی."""

    _next_response = None
    _next_exception = None
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        type(self).calls.append({"url": url, **kwargs})
        if type(self)._next_exception is not None:
            raise type(self)._next_exception
        return type(self)._next_response


@pytest.fixture(autouse=True)
def _reset_fake_client():
    _FakeAsyncClient._next_response = None
    _FakeAsyncClient._next_exception = None
    _FakeAsyncClient.calls = []
    yield


@pytest.fixture(autouse=True)
def _default_no_keys_configured(monkeypatch):
    """پیش‌فرض هر تست: هیچ کلیدی تنظیم نشده — هر تست خودش کلیدهای لازم را ست می‌کند."""
    monkeypatch.setattr(config, "GOOGLE_VISION_API_KEY", None)
    monkeypatch.setattr(config, "AZURE_VISION_KEY", None)
    monkeypatch.setattr(config, "AZURE_VISION_ENDPOINT", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(config, "OCR_PROVIDER_ORDER", ["google", "azure", "groq_vision"])
    monkeypatch.setattr(ocr_service, "httpx", SimpleNamespace(
        AsyncClient=_FakeAsyncClient,
        Timeout=lambda *a, **k: None,
    ))


@pytest.mark.asyncio
async def test_extract_text_raises_unavailable_when_nothing_configured():
    with pytest.raises(ocr_service.OcrServiceUnavailable):
        await ocr_service.extract_text(b"fake-image-bytes")


@pytest.mark.asyncio
async def test_extract_text_returns_google_result_when_configured(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_VISION_API_KEY", "fake-google-key")
    _FakeAsyncClient._next_response = _FakeResponse(
        {"responses": [{"fullTextAnnotation": {"text": "متن آزمایشی"}}]}
    )

    result = await ocr_service.extract_text(b"fake-image-bytes")

    assert result.text == "متن آزمایشی"
    assert result.provider == "google"


@pytest.mark.asyncio
async def test_extract_text_skips_unconfigured_google_and_uses_azure(monkeypatch):
    monkeypatch.setattr(config, "AZURE_VISION_KEY", "fake-azure-key")
    monkeypatch.setattr(config, "AZURE_VISION_ENDPOINT", "https://example.cognitiveservices.azure.com")
    _FakeAsyncClient._next_response = _FakeResponse(
        {"readResult": {"blocks": [{"lines": [{"text": "خط اول"}, {"text": "خط دوم"}]}]}}
    )

    result = await ocr_service.extract_text(b"fake-image-bytes")

    assert result.text == "خط اول\nخط دوم"
    assert result.provider == "azure"


@pytest.mark.asyncio
async def test_extract_text_falls_through_to_next_provider_on_empty_result(monkeypatch):
    """اگر لایه‌ی اول بدون خطا ولی با متن خالی برگردد، باید لایه‌ی بعدی
    امتحان شود (تصمیم طراحی: اولویت با recall است، نه توقف زودهنگام)."""
    monkeypatch.setattr(config, "GOOGLE_VISION_API_KEY", "fake-google-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "OCR_PROVIDER_ORDER", ["google", "groq_vision"])

    _FakeAsyncClient._next_response = _FakeResponse({"responses": [{}]})  # بدون fullTextAnnotation

    fake_choice = SimpleNamespace(message=SimpleNamespace(content="متن از Groq"))
    mock_completion = AsyncMock(return_value=SimpleNamespace(choices=[fake_choice]))
    monkeypatch.setattr(ocr_service, "litellm", SimpleNamespace(acompletion=mock_completion))

    result = await ocr_service.extract_text(b"fake-image-bytes")

    assert result.text == "متن از Groq"
    assert result.provider == "groq_vision"


@pytest.mark.asyncio
async def test_extract_text_falls_through_to_next_provider_on_error(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_VISION_API_KEY", "fake-google-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "OCR_PROVIDER_ORDER", ["google", "groq_vision"])

    _FakeAsyncClient._next_exception = RuntimeError("network boom")

    fake_choice = SimpleNamespace(message=SimpleNamespace(content="متن از Groq"))
    mock_completion = AsyncMock(return_value=SimpleNamespace(choices=[fake_choice]))
    monkeypatch.setattr(ocr_service, "litellm", SimpleNamespace(acompletion=mock_completion))

    result = await ocr_service.extract_text(b"fake-image-bytes")

    assert result.text == "متن از Groq"
    assert result.provider == "groq_vision"


@pytest.mark.asyncio
async def test_extract_text_returns_empty_result_when_all_configured_providers_find_nothing(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_VISION_API_KEY", "fake-google-key")
    monkeypatch.setattr(config, "OCR_PROVIDER_ORDER", ["google"])
    _FakeAsyncClient._next_response = _FakeResponse({"responses": [{}]})

    result = await ocr_service.extract_text(b"fake-image-bytes")

    assert result.text == ""
    assert result.provider is None


@pytest.mark.asyncio
async def test_google_vision_sends_persian_language_hint(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_VISION_API_KEY", "fake-google-key")
    _FakeAsyncClient._next_response = _FakeResponse(
        {"responses": [{"fullTextAnnotation": {"text": "ok"}}]}
    )

    await ocr_service.extract_text(b"fake-image-bytes")

    sent_payload = _FakeAsyncClient.calls[0]["json"]
    assert sent_payload["requests"][0]["imageContext"]["languageHints"] == ["fa"]
    assert sent_payload["requests"][0]["features"][0]["type"] == "DOCUMENT_TEXT_DETECTION"


@pytest.mark.asyncio
async def test_azure_vision_uses_read_feature_and_subscription_key_header(monkeypatch):
    monkeypatch.setattr(config, "AZURE_VISION_KEY", "fake-azure-key")
    monkeypatch.setattr(config, "AZURE_VISION_ENDPOINT", "https://example.cognitiveservices.azure.com/")
    _FakeAsyncClient._next_response = _FakeResponse({"readResult": {"blocks": []}})

    await ocr_service.extract_text(b"fake-image-bytes")

    call = _FakeAsyncClient.calls[0]
    assert call["url"] == "https://example.cognitiveservices.azure.com/computervision/imageanalysis:analyze"
    assert call["params"]["features"] == "read"
    assert call["headers"]["Ocp-Apim-Subscription-Key"] == "fake-azure-key"


@pytest.mark.asyncio
async def test_groq_vision_uses_configured_model(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "OCR_PROVIDER_ORDER", ["groq_vision"])
    monkeypatch.setattr(config, "OCR_VISION_MODEL", "groq/qwen/qwen3.6-27b")

    fake_choice = SimpleNamespace(message=SimpleNamespace(content="متن تشخیص‌داده‌شده"))
    mock_completion = AsyncMock(return_value=SimpleNamespace(choices=[fake_choice]))
    monkeypatch.setattr(ocr_service, "litellm", SimpleNamespace(acompletion=mock_completion))

    result = await ocr_service.extract_text(b"fake-image-bytes")

    assert result.text == "متن تشخیص‌داده‌شده"
    _, kwargs = mock_completion.call_args
    assert kwargs["model"] == "groq/qwen/qwen3.6-27b"
    # اولین آیتم content باید پرامپت متنی و دومی تصویر base64 باشد
    content = kwargs["messages"][0]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


# --- تمایز خطای واقعی provider از «واقعاً متنی نبود» ---

@pytest.mark.asyncio
async def test_extract_text_raises_provider_error_when_only_configured_layer_fails(monkeypatch):
    """تفاوت کلیدی با test_extract_text_returns_empty_result_when_all_configured_providers_find_nothing:
    آنجا Google بدون خطا خالی برمی‌گشت (واقعاً متنی نبود)؛ اینجا Google با خطای
    واقعی مواجه می‌شود — نتیجه باید OcrProviderError باشد، نه یک OcrResult
    خالیِ به‌ظاهر معتبر."""
    monkeypatch.setattr(config, "GOOGLE_VISION_API_KEY", "fake-google-key")
    monkeypatch.setattr(config, "OCR_PROVIDER_ORDER", ["google"])
    _FakeAsyncClient._next_exception = RuntimeError("network boom")

    with pytest.raises(ocr_service.OcrProviderError):
        await ocr_service.extract_text(b"fake-image-bytes")


@pytest.mark.asyncio
async def test_extract_text_provider_error_takes_precedence_even_if_later_layer_also_empty(monkeypatch):
    """اگر لایه‌ی اول خطای واقعی بدهد و لایه‌ی دوم (پیکربندی‌شده) بدون خطا ولی
    خالی برگرداند، نتیجه‌ی نهایی همچنان باید OcrProviderError باشد — چون حداقل
    یک لایه خطای واقعی داشته، نمی‌توان با اطمینان گفت «واقعاً متنی نبود»."""
    monkeypatch.setattr(config, "GOOGLE_VISION_API_KEY", "fake-google-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setattr(config, "OCR_PROVIDER_ORDER", ["google", "groq_vision"])

    _FakeAsyncClient._next_exception = RuntimeError("google network boom")
    fake_choice = SimpleNamespace(message=SimpleNamespace(content=""))
    mock_completion = AsyncMock(return_value=SimpleNamespace(choices=[fake_choice]))
    monkeypatch.setattr(ocr_service, "litellm", SimpleNamespace(acompletion=mock_completion))

    with pytest.raises(ocr_service.OcrProviderError):
        await ocr_service.extract_text(b"fake-image-bytes")


@pytest.mark.asyncio
async def test_is_configured_true_when_any_single_key_present(monkeypatch):
    assert ocr_service.is_configured() is False  # فیکسچر پیش‌فرض: هیچ کلیدی نیست

    monkeypatch.setattr(config, "GROQ_API_KEY", "fake-groq-key")
    assert ocr_service.is_configured() is True
