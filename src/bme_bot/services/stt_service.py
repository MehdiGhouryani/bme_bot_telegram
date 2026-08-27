# src/bme_bot/services/stt_service.py
# زنجیره تبدیل ویس به متن فارسی: ElevenLabs → Groq → Deepgram → AssemblyAI
# → Azure → Google Cloud → wit.ai → Google (غیررسمی) — ترتیب از config.
#
# این ماژول عیناً منطق تصمیم‌گیریِ تحقیق (ترتیب زنجیره، تشخیص "شکست" هر
# سرویس، کجا تبدیل OGG→WAV واقعاً لازم است) را حفظ می‌کند، ولی به شکل یک
# ماژول async نوشته شده — هم‌شکل ocr_service.py (خواهرش در منوی ابزارها) —
# نه پیاده‌سازی sync اولیه‌ای که برای بررسی تحویل داده شده بود. دلیل: بقیه‌ی
# پروژه (ocr_service.py، ai_service.py) کاملاً روی httpx.AsyncClient/await
# بنا شده؛ فراخوانی مستقیم requests.post/time.sleep/subprocess.run از یک
# handler async کل event loop ربات را برای مدت هر تماس شبکه قفل می‌کرد —
# نه فقط برای همان کاربر، برای همه‌ی کاربرهای همزمان بات.
#
# retry/backoff: از utils/retry.py (async_retry) استفاده می‌شود — همان
# ماژول مشترکی که از قبل در ai_service.py و equipment_callbacks.py استفاده
# می‌شود؛ ocr_service.py با یک پیاده‌سازی محلی مستقل (_with_retry/_is_retryable)
# از این الگو منحرف شده بود، ولی آن انحراف قبلی است و اینجا تکرار نشد.
#
# تصمیم عمدی نسبت به تحقیق اولیه: تایر Google Cloud رسمی دیگر
# sampleRateHertz را برای OGG_OPUS هاردکد نمی‌کند — طبق مستندات Google،
# نرخ نمونه‌برداری در همان کانتینر OGG موجود است و اگر مقدار دستی با آن
# نخواند، کل درخواست رد می‌شود (نه فقط افت دقت). این مورد هنوز باید با یک
# ویس واقعی تلگرام عملاً تست شود.

from __future__ import annotations

import asyncio
import base64
import dataclasses
import importlib.util
import json
import logging

import httpx

from .. import config
from ..utils.retry import async_retry

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_RETRIES = 1  # صدا سنگین‌تر از عکس است؛ عمداً کمتر از OCR (که ۲ است)

_FFMPEG_TIMEOUT_SECONDS = 30
_ASSEMBLYAI_POLL_INTERVAL_SECONDS = 2
_ASSEMBLYAI_POLL_MAX_ATTEMPTS = 15  # حداکثر ۳۰ ثانیه انتظار

# علاوه بر ویس‌نوت تلگرام (همیشه OGG)، فایل آپلودی دلخواه (mp3/m4a/wav/...)
# هم ممکن است به transcribe() برسد (جزوه‌سازی از فایل آپلودی، نه فقط ویس‌نوت).
# این نگاشت پسوند→mimetype فقط شامل فرمت‌هایی است که مستندات رسمی Groq
# (تایر اصلی) و ElevenLabs (تایر اول) صراحتاً پشتیبانی‌شان را تایید کرده‌اند؛
# روی mimetypes سیستم‌عامل تکیه نشد چون بین سرورها یکسان نیست.
_EXTENSION_TO_MIMETYPE = {
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "opus": "audio/ogg",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "mp4": "audio/mp4",
    "wav": "audio/wav",
    "webm": "audio/webm",
    "flac": "audio/flac",
    "mpga": "audio/mpeg",
    "mpeg": "audio/mpeg",
}


def _guess_mimetype(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _EXTENSION_TO_MIMETYPE.get(ext, "application/octet-stream")


class SttProviderNotConfigured(Exception):
    """کلید این لایه در .env نیست — بی‌صدا رد می‌شود."""


class SttServiceUnavailable(Exception):
    """هیچ لایه‌ای پیکربندی نشده."""


class SttProviderError(Exception):
    """حداقل یک لایه‌ی پیکربندی‌شده خطای واقعی داد و متنی پیدا نشد."""


def is_configured() -> bool:
    """آیا حداقل یک لایه از زنجیره واقعاً قابل‌استفاده است؟

    نکته‌ی مهم: google_unofficial به هیچ کلیدی نیاز ندارد - فقط به نصب‌بودن
    پکیج speech_recognition. این تابع باید همان چیزی را بسنجد که transcribe()
    واقعاً امتحان می‌کند؛ اگر این تایر را نادیده بگیرد، در دقیقاً همان
    وضعیتی که الان دارید (هیچ کلیدی هنوز ست نشده) هندلر به‌اشتباه به کاربر
    می‌گوید سرویس در دسترس نیست، در حالی که تایر آخرِ کاملاً رایگان در واقع
    کار می‌کرد."""
    return bool(
        config.ELEVENLABS_API_KEY
        or config.GROQ_API_KEY
        or config.DEEPGRAM_API_KEY
        or config.ASSEMBLYAI_API_KEY
        or (config.AZURE_SPEECH_KEY and config.AZURE_SPEECH_REGION)
        or config.GOOGLE_STT_API_KEY
        or config.WIT_AI_TOKEN
        or (
            "google_unofficial" in config.STT_PROVIDER_ORDER
            and importlib.util.find_spec("speech_recognition") is not None
        )
    )


@dataclasses.dataclass
class SttResult:
    text: str
    provider: str | None  # None = متنی پیدا نشد


# ----------------------------------------------------------------------
# ابزار کمکی: تبدیل OGG به WAV در حافظه (بدون فایل موقت روی دیسک) — فقط
# تایرهای Azure و Google-غیررسمی به آن نیاز دارند. برخلاف نسخه‌ی اولیه
# (subprocess.run + فایل موقت)، اینجا با pipe کاملاً async و بدون I/O
# دیسک انجام می‌شود؛ هم رفع می‌کند مشکل قبلی (TimeoutExpired ناگرفته که
# قرارداد خطای زنجیره را نقض می‌کرد)، هم نشتی فایل ناقص را از بین می‌برد.
# ----------------------------------------------------------------------
async def _ogg_to_wav_bytes(ogg_bytes: bytes) -> bytes:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", "pipe:0", "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise SttProviderError("ffmpeg نصب نیست (apt install ffmpeg)")

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=ogg_bytes), timeout=_FFMPEG_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise SttProviderError("تبدیل ffmpeg بیش از حد طول کشید")

    if proc.returncode != 0 or not stdout:
        raise SttProviderError(f"تبدیل ffmpeg شکست خورد: {stderr.decode(errors='ignore')[:200]}")
    return stdout


# ----------------------------------------------------------------------
# تایر ۱: ElevenLabs Scribe — بهترین دقت، سهمیه‌ی رایگان کوچیک و مشترک
# بین همه‌ی کاربرهای بات (نه هرکاربر جدا).
# ----------------------------------------------------------------------
async def _try_elevenlabs(audio_bytes: bytes, filename: str) -> str:
    if not config.ELEVENLABS_API_KEY:
        raise SttProviderNotConfigured("elevenlabs")

    async def _call():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers={"xi-api-key": config.ELEVENLABS_API_KEY},
                files={"file": (filename, audio_bytes, _guess_mimetype(filename))},
                # language_code عمداً ارسال نمی‌شود - Scribe خودش زبون رو تشخیص می‌ده.
                data={"model_id": "scribe_v2"},
            )
        response.raise_for_status()
        return (response.json().get("text") or "").strip()

    return await async_retry(_call, retries=_MAX_RETRIES, label="stt.elevenlabs")


# ----------------------------------------------------------------------
# تایر ۲: Groq (Whisper large-v3) — ستون فقرات، سهمیه‌ی عظیم (۸ ساعت/روز،
# ولی زیرمحدودیت ۲ ساعت/ساعت هم دارد - در بار ترافیک بالا ممکن است زودتر
# از حد روزانه به ۴۲۹ بخورد).
# ----------------------------------------------------------------------
async def _try_groq(audio_bytes: bytes, filename: str) -> str:
    if not config.GROQ_API_KEY:
        raise SttProviderNotConfigured("groq")

    async def _call():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                files={"file": (filename, audio_bytes, _guess_mimetype(filename))},
                data={"model": "whisper-large-v3", "language": "fa"},
            )
        response.raise_for_status()
        return (response.json().get("text") or "").strip()

    return await async_retry(_call, retries=_MAX_RETRIES, label="stt.groq")


# ----------------------------------------------------------------------
# تایر ۳: Deepgram Nova-3 — credit یک‌باره ($۲۰۰)، پشتیبان.
# مهم: language=fa (مدل monolingual)، نه language=multi — multi از فارسی
# پشتیبانی نمی‌کند.
# ----------------------------------------------------------------------
async def _try_deepgram(audio_bytes: bytes, filename: str) -> str:
    if not config.DEEPGRAM_API_KEY:
        raise SttProviderNotConfigured("deepgram")

    async def _call():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={"model": "nova-3", "language": "fa"},
                headers={
                    "Authorization": f"Token {config.DEEPGRAM_API_KEY}",
                    "Content-Type": _guess_mimetype(filename),
                },
                content=audio_bytes,
            )
        response.raise_for_status()
        data = response.json()
        try:
            return data["results"]["channels"][0]["alternatives"][0]["transcript"].strip()
        except (KeyError, IndexError):
            raise SttProviderError("Deepgram: فرمت پاسخ غیرمنتظره")

    return await async_retry(_call, retries=_MAX_RETRIES, label="stt.deepgram")


# ----------------------------------------------------------------------
# تایر ۴: AssemblyAI — credit یک‌باره‌ی کوچیک‌تر ($۵۰)، سه‌مرحله‌ای (آپلود
# → ساخت transcript → poll). خودِ poll خارج از async_retry است (منتظر
# نتیجه‌ی یک job، نه تلاش مجدد یک درخواست شکست‌خورده).
# ----------------------------------------------------------------------
async def _try_assemblyai(audio_bytes: bytes, filename: str) -> str:
    if not config.ASSEMBLYAI_API_KEY:
        raise SttProviderNotConfigured("assemblyai")

    headers = {"authorization": config.ASSEMBLYAI_API_KEY}

    async def _upload():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://api.assemblyai.com/v2/upload", headers=headers, content=audio_bytes,
            )
        response.raise_for_status()
        return response.json()["upload_url"]

    audio_url = await async_retry(_upload, retries=_MAX_RETRIES, label="stt.assemblyai.upload")

    async def _create_transcript():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                "https://api.assemblyai.com/v2/transcript",
                headers=headers,
                json={"audio_url": audio_url, "language_code": "fa"},
            )
        response.raise_for_status()
        return response.json()["id"]

    transcript_id = await async_retry(
        _create_transcript, retries=_MAX_RETRIES, label="stt.assemblyai.create",
    )

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        for _ in range(_ASSEMBLYAI_POLL_MAX_ATTEMPTS):
            await asyncio.sleep(_ASSEMBLYAI_POLL_INTERVAL_SECONDS)
            poll_response = await client.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers,
            )
            poll_response.raise_for_status()
            poll = poll_response.json()
            if poll.get("status") == "completed":
                return (poll.get("text") or "").strip()
            if poll.get("status") == "error":
                raise SttProviderError(f"AssemblyAI: {poll.get('error')}")

    raise SttProviderError("AssemblyAI: timeout در انتظار نتیجه")


# ----------------------------------------------------------------------
# تایر ۵: Azure AI Speech — نیاز به کارت (F0)، نیاز به WAV.
# ----------------------------------------------------------------------
async def _try_azure(audio_bytes: bytes, filename: str) -> str:
    if not (config.AZURE_SPEECH_KEY and config.AZURE_SPEECH_REGION):
        raise SttProviderNotConfigured("azure")

    wav_bytes = await _ogg_to_wav_bytes(audio_bytes)
    url = (
        f"https://{config.AZURE_SPEECH_REGION}.stt.speech.microsoft.com"
        "/speech/recognition/conversation/cognitiveservices/v1"
    )

    async def _call():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                url,
                params={"language": "fa-IR"},
                headers={
                    "Ocp-Apim-Subscription-Key": config.AZURE_SPEECH_KEY,
                    "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
                },
                content=wav_bytes,
            )
        response.raise_for_status()
        result = response.json()
        if result.get("RecognitionStatus") != "Success":
            raise SttProviderError(f"Azure: {result.get('RecognitionStatus')}")
        return (result.get("DisplayText") or "").strip()

    return await async_retry(_call, retries=_MAX_RETRIES, label="stt.azure")


# ----------------------------------------------------------------------
# تایر ۶: Google Cloud STT — نیاز به کارت/billing.
# محدودیت عمدی: encoding پایین همیشه OGG_OPUS هاردکد است (طبق یافته‌ی
# بازبینی، sampleRateHertz حذف شد ولی encoding خودش باید درست باشد). برای
# فایل غیر-OGG (مثلاً mp3 آپلودی در فیچر جزوه‌سازی)، این تایر عمداً رد
# می‌شود به‌جای فرستادن encoding نادرست که حتماً شکست می‌خورد.
# ----------------------------------------------------------------------
async def _try_google(audio_bytes: bytes, filename: str) -> str:
    if not config.GOOGLE_STT_API_KEY:
        raise SttProviderNotConfigured("google")
    if not filename.lower().endswith((".ogg", ".oga", ".opus")):
        raise SttProviderNotConfigured("google")

    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    payload = {
        # sampleRateHertz عمداً ارسال نمی‌شود؛ برای OGG_OPUS از هدر خودِ
        # کانتینر خوانده می‌شود - رفع یافته‌ی بازبینی نسبت به تحقیق اولیه.
        "config": {"encoding": "OGG_OPUS", "languageCode": "fa-IR"},
        "audio": {"content": audio_b64},
    }

    async def _call():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                f"https://speech.googleapis.com/v1/speech:recognize?key={config.GOOGLE_STT_API_KEY}",
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        try:
            return data["results"][0]["alternatives"][0]["transcript"].strip()
        except (KeyError, IndexError):
            return ""  # صدا خیلی کوتاه/بی‌صدا بود - نه یک خطای واقعی

    return await async_retry(_call, retries=_MAX_RETRIES, label="stt.google")


# ----------------------------------------------------------------------
# تایر ۷: wit.ai — ته زنجیره، کاملاً رایگان.
# رفع باگ بازبینی: قبلاً OGG خام با Content-Type: audio/ogg مستقیم ارسال
# می‌شد، ولی تمام نمونه‌کدهای رسمی/جامعه‌ی wit.ai که پیدا شد بدون استثنا
# audio/wav می‌فرستند (حتی یک گزارش گیت‌هابی که صراحتاً OGG را قبل از
# ارسال به WAV تبدیل کرده). چون شواهد قطعی نبود ولی هم‌سو، برای امنیت
# همیشه تبدیل به WAV می‌شود - این هم آن ابهام را می‌بندد، هم به‌طور طبیعی
# ورودی غیر-OGG (فایل آپلودی جزوه‌سازی) را هم پشتیبانی می‌کند.
# ----------------------------------------------------------------------
async def _try_wit(audio_bytes: bytes, filename: str) -> str:
    if not config.WIT_AI_TOKEN:
        raise SttProviderNotConfigured("wit")

    wav_bytes = await _ogg_to_wav_bytes(audio_bytes)

    async def _call():
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                # نسخه‌ی API (v=...) نسخه‌ای است که تا اواسط ۲۰۲۶ در استفاده‌ی
                # واقعی تایید شد (بازبینی این فاز)؛ نسخه‌ی قبلی تحقیق اولیه
                # (20240304) بیش از ۲ سال قدیمی‌تر بود. قبل از production
                # دوباره در مستندات wit.ai چک شود - این پارامتر مدام تغییر می‌کند.
                "https://api.wit.ai/speech?v=20260505",
                headers={
                    "Authorization": f"Bearer {config.WIT_AI_TOKEN}",
                    "Content-Type": "audio/wav",
                },
                content=wav_bytes,
            )
        response.raise_for_status()
        # پاسخ wit.ai می‌تواند چند JSON پشت‌سرهم باشد (streaming)؛ آخرین
        # قطعه‌ی معتبر برداشته می‌شود.
        last_valid = None
        for line in response.text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                last_valid = json.loads(line)
            except ValueError:
                continue
        if last_valid and last_valid.get("text"):
            return last_valid["text"].strip()
        return ""

    return await async_retry(_call, retries=_MAX_RETRIES, label="stt.wit")


# ----------------------------------------------------------------------
# تایر ۸ (آخر): Google Web Speech غیررسمی — کاملاً رایگان، بدون کلید.
# این یک endpoint غیررسمی/reverse-engineered است که فقط از طریق پکیج sync
# SpeechRecognition در دسترس است (بدون معادل async رسمی) - به همین دلیل
# تنها تایری است که به‌جای httpx، از asyncio.to_thread دور یک تابع sync
# استفاده می‌کند؛ این طبق طرح تایید‌شده است، نه یک عقب‌گرد به سبک sync.
# ----------------------------------------------------------------------
def _blocking_recognize_google_unofficial(wav_bytes: bytes) -> str:
    import io

    import speech_recognition as sr

    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio, language="fa-IR").strip()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        raise SttProviderError(f"Google غیررسمی: {e}")


async def _try_google_unofficial(audio_bytes: bytes, filename: str) -> str:
    if importlib.util.find_spec("speech_recognition") is None:
        raise SttProviderNotConfigured("google_unofficial")

    wav_bytes = await _ogg_to_wav_bytes(audio_bytes)
    return await asyncio.to_thread(_blocking_recognize_google_unofficial, wav_bytes)


_PROVIDER_FUNCS = {
    "elevenlabs": _try_elevenlabs,
    "groq": _try_groq,
    "deepgram": _try_deepgram,
    "assemblyai": _try_assemblyai,
    "azure": _try_azure,
    "google": _try_google,
    "wit": _try_wit,
    "google_unofficial": _try_google_unofficial,
}


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> SttResult:
    """اولین متن غیرخالی از زنجیره را برمی‌گرداند.

    filename: نام/پسوند واقعی فایل (پیش‌فرض voice.ogg برای ویس‌نوت تلگرام،
    که رفتار فیچر STT فعلی را کاملاً دست‌نخورده نگه می‌دارد). فیچرهایی که
    فایل آپلودی دلخواه (mp3/m4a/wav/...) می‌گیرند (مثل جزوه‌سازی)، پسوند
    واقعی را همین‌جا پاس می‌دهند تا هر تایر Content-Type/فرمت درست بفرستد.

    - متن خالی بدون خطا → لایه بعدی امتحان می‌شود.
    - همه خالی و بدون خطا → SttResult("", None)
    - حداقل یک خطای واقعی + بدون متن → SttProviderError
    - هیچ لایه‌ای پیکربندی نشده → SttServiceUnavailable
    """
    attempted_any = False
    last_error: Exception | None = None

    for name in config.STT_PROVIDER_ORDER:
        func = _PROVIDER_FUNCS.get(name)
        if func is None:
            logger.warning("STT unknown provider in order: %r", name)
            continue

        try:
            text = await func(audio_bytes, filename)
        except SttProviderNotConfigured:
            logger.debug("STT [%s] not configured — skip", name)
            continue
        except Exception as e:
            logger.warning("STT [%s] failed: %s", name, e)
            last_error = e
            attempted_any = True
            continue

        attempted_any = True
        text = (text or "").strip()
        if text:
            logger.info("STT ok via [%s] (%d chars)", name, len(text))
            return SttResult(text=text, provider=name)
        logger.debug("STT [%s] returned empty — try next", name)

    if not attempted_any:
        raise SttServiceUnavailable("هیچ سرویس تبدیل ویس به متن پیکربندی نشده است.") from last_error

    if last_error is not None:
        raise SttProviderError("سرویس تبدیل ویس به متن با خطا مواجه شد؛ نتیجه نامعتبر است.") from last_error

    return SttResult(text="", provider=None)
