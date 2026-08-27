# src/bme_bot/utils/retry.py
# retry با backoff برای عملیات گذرا (timeout / شبکه / 5xx).

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE_NAMES = (
    "timeout", "timedout", "network", "connection", "ratelimit",
    "retryafter", "toomanyrequests", "serviceunavailable",
)
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def is_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if any(k in name or k in msg for k in _RETRYABLE_NAMES):
        return True
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    if status in _RETRYABLE_STATUS:
        return True
    mod = type(exc).__module__ or ""
    if "telegram" in mod and any(k in name for k in ("timedout", "network", "retryafter")):
        return True
    return False


async def async_retry(
    factory: Callable[[], Awaitable[T]],
    *,
    retries: int = 2,
    base_delay: float = 0.7,
    label: str = "op",
) -> T:
    """factory را تا retries+1 بار صدا می‌زند؛ فقط روی خطای گذرا تکرار می‌کند."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await factory()
        except Exception as e:
            last = e
            if attempt < retries and is_retryable(e):
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "%s attempt %d/%d failed: %s — sleep %.1fs",
                    label, attempt + 1, retries + 1, e, delay,
                )
                await asyncio.sleep(delay)
                continue
            raise
    raise last  # type: ignore[misc]