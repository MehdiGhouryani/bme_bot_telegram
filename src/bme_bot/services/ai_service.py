# src/bme_bot/services/ai_service.py
# فراخوانی زنجیره AI از طریق LiteLLM (Gemini → fallbackها).

from __future__ import annotations

import logging

import litellm

from .. import config
from ..utils import messages
from ..utils.retry import async_retry

logger = logging.getLogger(__name__)

PRIMARY_MODEL = config.AI_PRIMARY_MODEL
FALLBACK_MODELS = config.AI_FALLBACK_MODELS

NO_API_KEY_MESSAGE = messages.AI_UNAVAILABLE

if not config.GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY missing — AI primary layer unavailable")


class AIResponseEmpty(Exception):
    def __init__(self, blocked: bool = False):
        super().__init__("empty AI response")
        self.blocked = blocked


class AIServiceUnavailable(Exception):
    def __init__(self, message: str = NO_API_KEY_MESSAGE):
        super().__init__(message)


async def ask(user_question: str, system_prompt: str) -> tuple[str, str]:
    """(متن پاسخ، نام مدل موفق). خطاهای شبکه بعد از کل زنجیره با retry بیرونی."""
    if not config.GEMINI_API_KEY:
        raise AIServiceUnavailable()

    async def _call():
        return await litellm.acompletion(
            model=PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
            fallbacks=FALLBACK_MODELS,
        )

    try:
        response = await async_retry(_call, retries=1, base_delay=1.2, label="ai.ask")
    except Exception as e:
        logger.warning("AI chain failed after retries: %s", e)
        raise

    choice = response.choices[0]
    text = choice.message.content

    if not text:
        blocked = getattr(choice, "finish_reason", None) == "content_filter"
        raise AIResponseEmpty(blocked=blocked)

    logger.info("AI ok via model=%s (%d chars)", response.model, len(text))
    return text, response.model

async def test_all_models() -> list[tuple[str, bool, str]]:
    """هر مدل (اصلی + همه‌ی fallback ها) رو *مستقل و جدا از هم* با یه سوال
    مینیمال تست می‌کنه — برخلاف ask() که با اولین موفقیت متوقف می‌شه (و با
    fallbacks=... به litellm خودش زنجیره رو مدیریت می‌کنه، نه یه حلقه‌ی
    دستی)، اینجا هر مدل با یه فراخوانی litellm.acompletion جدا (بدون
    fallbacks) صدا زده می‌شه تا سهم واقعی هرکدوم معلوم بشه.

    این دقیقاً همون چیزیه که اگه از قبل بود، خرابی مدل gemini-2.5-flash رو
    (۴۰۴ روی *هر* درخواست) با یه تست دستی همون لحظه لو می‌داد، نه فقط از
    راه خوندن دستی لاگ production چند روز بعد.

    (نام مدل, موفق بود یا نه, پیام کوتاه). هیچ‌کدوم raise نمی‌کنه —
    شکست یه مدل نباید جلوی تست بقیه رو بگیره."""
    results = []
    for model in [PRIMARY_MODEL, *FALLBACK_MODELS]:
        try:
            await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": "سلام"}],
                max_tokens=5,
            )
            results.append((model, True, "OK"))
        except Exception as e:
            results.append((model, False, str(e)[:150]))
    return results
