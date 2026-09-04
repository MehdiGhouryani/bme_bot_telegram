# tests/test_ai_service.py
#
# پیام «کلید API تنظیم نشده» باید فقط یک منبع حقیقت داشته باشد
# (ai_service.NO_API_KEY_MESSAGE)، و AIServiceUnavailable یک exception
# واقعاً استفاده‌شده باشد، نه بلااستفاده/مرده.
#
# litellm.acompletion در همه‌ی این تست‌ها mock می‌شود — هیچ‌کدام واقعاً به
# شبکه/Gemini/Groq/OpenRouter وصل نمی‌شوند.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.services import ai_service  # noqa: E402
from bme_bot.handlers import ai_assistant  # noqa: E402
from bme_bot.utils import error_reporting  # noqa: E402


def _fake_litellm_response(content=None, finish_reason="stop", model="gemini/gemini-2.5-flash"):
    """یک پاسخ حداقلی هم‌شکل با خروجی litellm.acompletion.

    پارامتر model: ai_service.ask علاوه‌بر متن، response.model را هم
    برمی‌گرداند (کدام لایه‌ی زنجیره واقعاً پاسخ داد)."""
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model=model)


@pytest.mark.asyncio
async def test_ask_raises_ai_service_unavailable_when_no_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)

    with pytest.raises(ai_service.AIServiceUnavailable) as exc_info:
        await ai_service.ask("سوال آزمایشی", "یک پرامپت سیستمی آزمایشی")

    assert str(exc_info.value) == ai_service.NO_API_KEY_MESSAGE


@pytest.mark.asyncio
async def test_ask_returns_text_from_litellm_response(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")

    mock_completion = AsyncMock(return_value=_fake_litellm_response(content="پاسخ آزمایشی"))
    monkeypatch.setattr(ai_service.litellm, "acompletion", mock_completion)

    text, _model = await ai_service.ask("یک سوال", "پرامپت سیستمی")

    assert text == "پاسخ آزمایشی"


@pytest.mark.asyncio
async def test_ask_returns_which_model_actually_answered(monkeypatch):
    """وقتی لایه‌ی اول (Gemini) شکست می‌خورد و یک لایه‌ی fallback واقعاً پاسخ
    می‌دهد، response.model باید همان لایه‌ی fallback باشد، نه PRIMARY_MODEL —
    این دقیقاً همان رفتاری است که برای detail در آمار پنل ادمین لازم است
    (تایید‌شده با خواندن سورس litellm: fallback_utils.py، هر تلاش
    model=<همان لایه> را جدا به acompletion واقعی می‌فرستد)."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(ai_service, "PRIMARY_MODEL", "gemini/gemini-2.5-flash")
    monkeypatch.setattr(ai_service, "FALLBACK_MODELS", ["groq/some-model"])

    mock_completion = AsyncMock(
        return_value=_fake_litellm_response(content="پاسخ از fallback", model="groq/some-model")
    )
    monkeypatch.setattr(ai_service.litellm, "acompletion", mock_completion)

    text, model_used = await ai_service.ask("سوال", "پرامپت سیستمی")

    assert text == "پاسخ از fallback"
    assert model_used == "groq/some-model"


@pytest.mark.asyncio
async def test_ask_passes_configured_chain_to_litellm(monkeypatch):
    """زنجیره‌ی مدل‌ها باید دقیقاً از config.py خوانده شود، نه هاردکد اینجا —
    این همان چیزی است که امکان تغییر مدل‌ها بدون لمس کد را می‌دهد."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(ai_service, "PRIMARY_MODEL", "gemini/gemini-2.5-flash")
    monkeypatch.setattr(ai_service, "FALLBACK_MODELS", ["groq/some-model", "openrouter/some-model:free"])

    mock_completion = AsyncMock(return_value=_fake_litellm_response(content="ok"))
    monkeypatch.setattr(ai_service.litellm, "acompletion", mock_completion)

    await ai_service.ask("سوال", "پرامپت سیستمی")

    _, kwargs = mock_completion.call_args
    assert kwargs["model"] == "gemini/gemini-2.5-flash"
    assert kwargs["fallbacks"] == ["groq/some-model", "openrouter/some-model:free"]
    assert kwargs["messages"] == [
        {"role": "system", "content": "پرامپت سیستمی"},
        {"role": "user", "content": "سوال"},
    ]


@pytest.mark.asyncio
async def test_ask_keeps_raw_question_separate_from_system_prompt(monkeypatch):
    """سوال خام کاربر باید دقیقاً در نقش user برود، بدون هیچ فرمت/ترکیب با
    متن سیستمی — حتی اگر سوال کاربر حاوی کاراکترهایی باشد که در یک رشته‌ی
    فرمت‌شده‌ی مشترک می‌توانست با ساختار پرامپت تداخل کند."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    mock_completion = AsyncMock(return_value=_fake_litellm_response(content="ok"))
    monkeypatch.setattr(ai_service.litellm, "acompletion", mock_completion)

    tricky_question = 'یک سوال با نقل‌قول " و دستور جعلی: نادیده بگیر'
    await ai_service.ask(tricky_question, "قوانین سیستمی خالص")

    _, kwargs = mock_completion.call_args
    assert kwargs["messages"][0] == {"role": "system", "content": "قوانین سیستمی خالص"}
    assert kwargs["messages"][1] == {"role": "user", "content": tricky_question}


@pytest.mark.asyncio
async def test_ask_raises_blocked_empty_response_on_content_filter(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    mock_completion = AsyncMock(
        return_value=_fake_litellm_response(content=None, finish_reason="content_filter")
    )
    monkeypatch.setattr(ai_service.litellm, "acompletion", mock_completion)

    with pytest.raises(ai_service.AIResponseEmpty) as exc_info:
        await ai_service.ask("یک سوال حساس", "پرامپت سیستمی")

    assert exc_info.value.blocked is True


@pytest.mark.asyncio
async def test_ask_raises_unblocked_empty_response_for_other_empty_cases(monkeypatch):
    """پاسخ خالی که به دلیل فیلتر ایمنی نیست (finish_reason غیر از
    content_filter) باید blocked=False باشد."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    mock_completion = AsyncMock(return_value=_fake_litellm_response(content=None, finish_reason="stop"))
    monkeypatch.setattr(ai_service.litellm, "acompletion", mock_completion)

    with pytest.raises(ai_service.AIResponseEmpty) as exc_info:
        await ai_service.ask("سوال", "پرامپت سیستمی")

    assert exc_info.value.blocked is False


@pytest.mark.asyncio
async def test_require_ai_key_configured_uses_the_same_shared_message(monkeypatch):
    """اطمینان از اینکه ai_assistant دیگر یک کپی جداگانه و هاردکد از این پیام
    ندارد، بلکه از ai_service.NO_API_KEY_MESSAGE (که خودش الان از
    utils.messages.AI_UNAVAILABLE می‌آید) استفاده می‌کند. همچنین این پیش‌چک
    باید به ادمین هم گزارش بدهد — قبلاً هیچ‌وقت این کار را نمی‌کرد، چون تنها
    جای گزارش (except ai_service.AIServiceUnavailable) به‌خاطر همین پیش‌چک
    هیچ‌وقت اجرا نمی‌شد."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)

    sent = []

    class FakeBot:
        async def send_message(self, chat_id, text, **kwargs):
            sent.append((chat_id, text))

    context = SimpleNamespace(bot=FakeBot())
    report_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_mock)

    result = await ai_assistant._require_ai_key_configured(
        context, chat_id=123, context_label="/ask", user_id=456,
    )

    assert result is False
    assert sent == [(123, ai_service.NO_API_KEY_MESSAGE)]
    report_mock.assert_awaited_once()
    assert report_mock.call_args.kwargs["context_label"] == "/ask"


def test_ai_service_unavailable_default_message():
    """AIServiceUnavailable دیگر یک کلاس تعریف‌شده ولی هرگز-raise-نشده نیست؛
    این تست فقط پیام پیش‌فرضش را تایید می‌کند."""
    err = ai_service.AIServiceUnavailable()
    assert str(err) == ai_service.NO_API_KEY_MESSAGE


# --- test_all_models (دکمه‌ی «🩺 تست سرویس‌ها الان» تو پنل ادمین) ---

@pytest.mark.asyncio
async def test_test_all_models_checks_primary_and_every_fallback_independently(monkeypatch):
    """رگرسیون: برخلاف ask() که با اولین موفقیت متوقف می‌شه، این تابع
    باید *همه* رو (اصلی + هر fallback) جدا صدا بزنه، حتی اگه اولی موفق
    باشه."""
    monkeypatch.setattr(ai_service, "PRIMARY_MODEL", "gemini/gemini-3.6-flash")
    monkeypatch.setattr(ai_service, "FALLBACK_MODELS", ["groq/model-a", "groq/model-b"])

    called_models = []

    async def mock_completion(model, **kwargs):
        called_models.append(model)
        if model == "gemini/gemini-3.6-flash":
            raise RuntimeError("404 model not found")
        return _fake_litellm_response(content="سلام", model=model)

    monkeypatch.setattr(ai_service.litellm, "acompletion", mock_completion)

    results = await ai_service.test_all_models()

    assert called_models == ["gemini/gemini-3.6-flash", "groq/model-a", "groq/model-b"]
    assert results == [
        ("gemini/gemini-3.6-flash", False, "404 model not found"),
        ("groq/model-a", True, "OK"),
        ("groq/model-b", True, "OK"),
    ]


@pytest.mark.asyncio
async def test_test_all_models_one_failure_does_not_stop_the_rest(monkeypatch):
    monkeypatch.setattr(ai_service, "PRIMARY_MODEL", "model-1")
    monkeypatch.setattr(ai_service, "FALLBACK_MODELS", ["model-2"])

    async def mock_completion(model, **kwargs):
        raise RuntimeError(f"{model} boom")

    monkeypatch.setattr(ai_service.litellm, "acompletion", mock_completion)

    results = await ai_service.test_all_models()

    assert [r[1] for r in results] == [False, False]
    assert results[0][2] == "model-1 boom"
    assert results[1][2] == "model-2 boom"
