# src/bme_bot/services/ocr_service.py
# زنجیره OCR: Google Vision → Azure → Groq Vision (ترتیب از config).

from __future__ import annotations

import asyncio
import base64
import dataclasses
import logging
import re

import httpx
import litellm

from .. import config

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 0.8  # ثانیه؛ exponential backoff

_OCR_VISION_PROMPT = (
    "تمام متن قابل‌مشاهده در این تصویر را دقیقاً همان‌طور که نوشته شده است "
    "استخراج کن و فقط همان متن را برگردان — بدون هیچ توضیح، مقدمه، یا جمله‌ی "
    "اضافه‌ی دیگر. اگر هیچ متنی در تصویر نیست، فقط یک رشته‌ی خالی برگردان."
)

# تگ‌های reasoning مدل‌های vision (مثل qwen)
_THINK_RE = re.compile(
    r"<think(?:ing)?>.*?</think(?:ing)?>",
    re.DOTALL | re.IGNORECASE,
)
_THINK_OPEN_RE = re.compile(r"</?think(?:ing)?>", re.IGNORECASE)


class OcrProviderNotConfigured(Exception):
    """کلید این لایه در .env نیست — بی‌صدا رد می‌شود."""


class OcrServiceUnavailable(Exception):
    """هیچ لایه‌ای پیکربندی نشده."""


class OcrProviderError(Exception):
    """حداقل یک لایه پیکربندی‌شده خطای واقعی داد و متنی پیدا نشد."""


def is_configured() -> bool:
    return bool(
        config.GOOGLE_VISION_API_KEY
        or config.AZURE_VISION_KEY
        or config.GROQ_API_KEY
        or config.GEMINI_API_KEY
    )


@dataclasses.dataclass
class OcrResult:
    text: str
    provider: str | None  # None = متنی پیدا نشد


def _strip_reasoning(text: str) -> str:
    """حذف بلوک‌های <think>/<thinking> و تگ‌های باقی‌مانده."""
    if not text:
        return ""
    cleaned = _THINK_RE.sub("", text)
    cleaned = _THINK_OPEN_RE.sub("", cleaned)
    return cleaned.strip()


def _is_retryable(exc: BaseException) -> bool:
    """خطاهای گذرا (timeout، 429، 5xx) قابل‌تلاش مجددند؛ 4xx دائمی نه."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError, asyncio.TimeoutError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    # litellm / عمومی
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if any(k in name or k in msg for k in ("timeout", "rate", "429", "503", "502", "overloaded")):
        return True
    if any(k in msg for k in ("401", "403", "unauthorized", "forbidden", "invalid api")):
        return False
    return False


async def _with_retry(name: str, coro_factory):
    """تلاش با backoff روی خطاهای گذرا. خطای دائمی فوراً بالا می‌رود."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return await coro_factory()
        except OcrProviderNotConfigured:
            raise
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES and _is_retryable(e):
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "OCR [%s] attempt %d/%d failed (retryable): %s — sleep %.1fs",
                    name, attempt + 1, _MAX_RETRIES + 1, e, delay,
                )
                await asyncio.sleep(delay)
                continue
            raise
    raise last_exc  # type: ignore[misc]


async def _try_google_vision(image_bytes: bytes) -> str:
    if not config.GOOGLE_VISION_API_KEY:
        raise OcrProviderNotConfigured("google")

    payload = {
        "requests": [{
            "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            "imageContext": {"languageHints": ["fa"]},
        }]
    }

    async def _call():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://vision.googleapis.com/v1/images:annotate",
                params={"key": config.GOOGLE_VISION_API_KEY},
                json=payload,
            )
        if response.status_code >= 400:
            # response.raise_for_status() پیام پیش‌فرضش شامل URL کامل
            # درخواسته — و چون Google Vision کلید رو به‌عنوان query param
            # می‌خواد (نه header، برخلاف بقیه‌ی سرویس‌های این پروژه)، یعنی
            # کلید خام تو اون پیام می‌افته و از اونجا به لاگ/هشدار ادمین
            # درز می‌کنه (تایید‌شده رو یه لاگ production واقعی). به‌جاش خودمون
            # با پیام sanitize‌شده raise می‌کنیم، ولی همچنان یه
            # httpx.HTTPStatusError واقعی با response واقعی — چون
            # _is_retryable پایین‌تر دقیقاً با isinstance(exc,
            # httpx.HTTPStatusError) و exc.response.status_code تشخیص
            # retryable/دائمی بودن (429/500/502/503/504) رو می‌ده؛ اگه اینجا
            # یه Exception عمومی بدیم، اون تشخیص دقیق از دست می‌ره.
            raise httpx.HTTPStatusError(
                f"Google Vision: {response.status_code} {response.reason_phrase}",
                request=response.request,
                response=response,
            )
        data = response.json()
        result = (data.get("responses") or [{}])[0]
        if result.get("error"):
            raise RuntimeError(f"Google Vision: {result['error']}")
        annotation = result.get("fullTextAnnotation")
        return annotation.get("text", "") if annotation else ""

    return await _with_retry("google", _call)


async def _try_azure_vision(image_bytes: bytes) -> str:
    if not (config.AZURE_VISION_KEY and config.AZURE_VISION_ENDPOINT):
        raise OcrProviderNotConfigured("azure")

    url = f"{config.AZURE_VISION_ENDPOINT.rstrip('/')}/computervision/imageanalysis:analyze"

    async def _call():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                url,
                params={"features": "read", "api-version": "2024-02-01"},
                headers={
                    "Ocp-Apim-Subscription-Key": config.AZURE_VISION_KEY,
                    "Content-Type": "application/octet-stream",
                },
                content=image_bytes,
            )
        response.raise_for_status()
        data = response.json()
        lines = [
            line.get("text", "")
            for block in data.get("readResult", {}).get("blocks", [])
            for line in block.get("lines", [])
        ]
        return "\n".join(lines)

    return await _with_retry("azure", _call)


async def _try_groq_vision(image_bytes: bytes) -> str:
    if not config.GROQ_API_KEY:
        raise OcrProviderNotConfigured("groq_vision")

    b64 = base64.b64encode(image_bytes).decode("ascii")

    async def _call():
        response = await litellm.acompletion(
            model=config.OCR_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
        )
        raw = response.choices[0].message.content or ""
        return _strip_reasoning(raw)

    return await _with_retry("groq_vision", _call)


async def _try_gemini_vision(image_bytes: bytes) -> str:
    # همون GEMINI_API_KEY لایه‌ی AI اصلی — بدون هزینه/ثبت‌نام اضافه. رجوع به
    # توضیح کامل در config.py برای این‌که چرا آخر صف پیش‌فرضه و چطور مستقلاً
    # تستش کنید.
    if not config.GEMINI_API_KEY:
        raise OcrProviderNotConfigured("gemini")

    b64 = base64.b64encode(image_bytes).decode("ascii")

    async def _call():
        response = await litellm.acompletion(
            model=config.OCR_GEMINI_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
        )
        raw = response.choices[0].message.content or ""
        return _strip_reasoning(raw)

    return await _with_retry("gemini", _call)


_PROVIDER_FUNCS = {
    "google": _try_google_vision,
    "azure": _try_azure_vision,
    "groq_vision": _try_groq_vision,
    "gemini": _try_gemini_vision,
}


async def extract_text(image_bytes: bytes) -> OcrResult:
    """اولین متن غیرخالی از زنجیره را برمی‌گرداند.

    - متن خالی بدون خطا → لایه بعدی امتحان می‌شود.
    - همه خالی و بدون خطا → OcrResult("", None)
    - حداقل یک خطای واقعی + بدون متن → OcrProviderError
    - هیچ لایه‌ای پیکربندی نشده → OcrServiceUnavailable
    """
    attempted_any = False
    last_error: Exception | None = None

    for name in config.OCR_PROVIDER_ORDER:
        func = _PROVIDER_FUNCS.get(name)
        if func is None:
            logger.warning("OCR unknown provider in order: %r", name)
            continue

        try:
            text = await func(image_bytes)
        except OcrProviderNotConfigured:
            logger.debug("OCR [%s] not configured — skip", name)
            continue
        except Exception as e:
            logger.warning("OCR [%s] failed: %s", name, e)
            last_error = e
            attempted_any = True
            continue

        attempted_any = True
        text = (text or "").strip()
        if text:
            logger.info("OCR ok via [%s] (%d chars)", name, len(text))
            return OcrResult(text=text, provider=name)
        logger.debug("OCR [%s] returned empty — try next", name)

    if not attempted_any:
        raise OcrServiceUnavailable(
            "هیچ سرویس OCR پیکربندی نشده است."
        ) from last_error

    if last_error is not None:
        raise OcrProviderError(
            "سرویس OCR با خطا مواجه شد؛ نتیجه نامعتبر است."
        ) from last_error

    return OcrResult(text="", provider=None)

# یه PNG سفید ۳۲×۳۲ مینیمال و معتبر — فقط برای تست اتصال/اعتبار کلید هر
# provider (test_all_providers)، نه استخراج متن واقعی. عمداً بزرگ‌تر از
# ۱×۱ پیکسل: بعضی API های vision یه تصویر خیلی کوچیک/بی‌محتوا رو با خطای
# نامرتبط به احراز هویت (مثلاً "image too small") رد می‌کنن که نتیجه‌ی
# تست رو گمراه‌کننده می‌کرد.
_TEST_IMAGE_PNG_32X32 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAJklEQVR42u3NMQ0AAAwDoPo33arYs"
    "QQMkB6LQCAQCAQCgUAg+BIMi1X0ptsIcT0AAAAASUVORK5CYII="
)


async def test_all_providers() -> list[tuple[str, bool | None, str]]:
    """هر provider *پیکربندی‌شده* رو (نه فقط اولی که موفق می‌شه) مستقیم و
    جدا از هم با یه عکس تستی مینیمال صدا می‌زنه — برخلاف extract_text که
    همین‌که یکی موفق شد متوقف می‌شه. برای دکمه‌ی «🩺 تست سرویس‌ها» تو پنل
    ادمین.

    (نام provider، True/False/None، پیام کوتاه) — None یعنی «پیکربندی
    نشده» (نه شکست واقعی؛ جدا از False نگه داشته شده تا تو نمایش نتیجه با
    یه خطای واقعی قاطی نشه)."""
    results = []
    for name, func in _PROVIDER_FUNCS.items():
        try:
            await func(_TEST_IMAGE_PNG_32X32)
            results.append((name, True, "OK"))
        except OcrProviderNotConfigured:
            results.append((name, None, "پیکربندی نشده"))
        except Exception as e:
            results.append((name, False, str(e)[:150]))
    return results
