# tests/test_ai_assistant_rich_message.py
#
# پوشش مهاجرت پیام نهایی /ask و /ai به sendRichMessage (رجوع به
# utils/rich_message.py و _send_reply_chunks در handlers/ai_assistant.py).
# پوشش رفتار خودِ draft streaming در test_ai_assistant_streaming.py است و
# پوشش محدودیت روزانه در test_ai_assistant_rate_limit.py — این فایل عمداً
# فقط روی مسیر ارسالِ پیام نهایی (rich → fallback مارک‌داون → fallback متن
# ساده) متمرکز است.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.constants import ChatType
from telegram.error import BadRequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import ai_usage_repository, feature_usage_repository  # noqa: E402
from bme_bot.handlers import ai_assistant  # noqa: E402
from bme_bot.services import ai_service  # noqa: E402
from bme_bot.utils import draft_stream  # noqa: E402


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(config, "AI_STREAMING_ENABLED", False)  # این فایل کاری به draft نداره
    monkeypatch.setattr(draft_stream, "_STEP_DELAY_SECONDS", 0)
    monkeypatch.setattr(ai_usage_repository, "check_ai_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(ai_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(ai_usage_repository, "increment_ai_usage", AsyncMock())
    monkeypatch.setattr(feature_usage_repository, "log_usage", AsyncMock())
    monkeypatch.setattr(
        ai_service, "ask", AsyncMock(return_value=("پاسخ حاوی | یک | جدول |", "gemini/gemini-3.6-flash")),
    )


def _fake_update_and_context(*, rich_message_ok, question_text="سوال تست"):
    """rich_message_ok=True یعنی sendRichMessage موفقه. برای شکست، یک
    Exception پاس بده (نه False) — چون send_rich_message دقیقاً مثل خودِ
    do_api_request واقعی فقط exception رو شکست می‌شمره، نه مقدار برگشتی؛
    یه mock که صرفاً False برمی‌گردونه (بدون raise) رفتار واقعی API رو
    درست شبیه‌سازی نمی‌کنه و send_rich_message همچنان True می‌فهمدش."""
    sent_messages = []

    class FakeBot:
        def __init__(self):
            self.rich_message_calls = []

            async def _do_api_request_side_effect(endpoint, data=None, **kwargs):
                if endpoint == "sendRichMessage":
                    self.rich_message_calls.append(data)
                    if rich_message_ok is not True:
                        raise rich_message_ok  # همیشه یه Exception (رجوع به docstring)
                    return True
                return True  # سایر endpointها (مثلاً در تست‌های دیگه) اهمیتی این‌جا ندارن

            self.do_api_request = AsyncMock(side_effect=_do_api_request_side_effect)

        async def send_message(self, chat_id, text, **kwargs):
            sent_messages.append((chat_id, text, kwargs.get("parse_mode")))
            return SimpleNamespace(message_id=1)

        async def delete_message(self, chat_id, message_id):
            pass

    bot = FakeBot()
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=555, type=ChatType.PRIVATE),
        effective_user=SimpleNamespace(id=4242),
    )
    context = SimpleNamespace(bot=bot, args=question_text.split())
    return update, context, bot, sent_messages


@pytest.mark.asyncio
async def test_ask_final_answer_sent_via_rich_message_when_it_succeeds():
    update, context, bot, sent_messages = _fake_update_and_context(rich_message_ok=True)

    await ai_assistant.ask_command(update, context)

    assert len(bot.rich_message_calls) == 1
    assert bot.rich_message_calls[0]["chat_id"] == 555
    assert bot.rich_message_calls[0]["rich_message"]["markdown"] == "پاسخ حاوی | یک | جدول |"
    # پیام نهایی نباید از مسیر قدیمی send_message هم رفته باشه — فقط پیام
    # موقتِ «در حال پردازش» مجازه که با متن جواب فرق داره.
    assert not any("پاسخ حاوی" in text for _, text, _ in sent_messages)


@pytest.mark.asyncio
async def test_ask_falls_back_to_markdown_when_rich_message_raises():
    """تنها مسیر واقع‌بینانه‌ی شکست: یه Exception واقعی (نه صرفاً یه مقدار
    falsy) — دقیقاً مثل PTB واقعی که روی خطای API استثنا پرت می‌کنه، نه
    این‌که مقدار برگشتی خاصی بده."""
    update, context, bot, sent_messages = _fake_update_and_context(
        rich_message_ok=Exception("TELEGRAM_DOWN"),
    )

    await ai_assistant.ask_command(update, context)

    assert len(bot.rich_message_calls) == 1  # تلاش شد، ولی ناموفق بود
    matching = [m for m in sent_messages if "پاسخ حاوی" in m[1]]
    assert len(matching) == 1
    assert matching[0][2] is not None  # parse_mode=MARKDOWN_V2 (مسیر قدیمی دست‌نخورده)


@pytest.mark.asyncio
async def test_ai_command_passes_reply_parameters_to_rich_message(monkeypatch):
    monkeypatch.setattr(ai_assistant, "is_admin", lambda user_id: True)
    update, context, bot, _ = _fake_update_and_context(rich_message_ok=True)
    original_message = SimpleNamespace(message_id=999, text="متن اصلی", reply_text=AsyncMock())
    update.message = SimpleNamespace(
        from_user=SimpleNamespace(id=4242),
        reply_to_message=original_message,
    )

    await ai_assistant.ai_command(update, context)

    assert len(bot.rich_message_calls) == 1
    assert bot.rich_message_calls[0]["reply_parameters"] == {"message_id": 999}
    original_message.reply_text.assert_not_called()  # چون مسیر rich موفق بود


@pytest.mark.asyncio
async def test_send_reply_chunks_still_falls_back_to_plain_text_on_bad_markdown(monkeypatch):
    """لایه‌ی سوم (fallback قدیمیِ خودِ MarkdownV2 → متن ساده روی
    BadRequest) باید حتی بعد از این مهاجرت دست‌نخورده کار کنه — یعنی وقتی
    هم rich message و هم MarkdownV2 شکست می‌خورن، آخرین لایه (متن ساده)
    همچنان پیام رو می‌رسونه."""
    update, context, bot, sent_messages = _fake_update_and_context(
        rich_message_ok=Exception("TELEGRAM_DOWN"),
    )

    real_send_message = bot.send_message

    async def flaky_send_message(chat_id, text, **kwargs):
        # فقط اولین تلاش MarkdownV2 برای *خودِ پاسخ نهایی* رو خراب می‌کنیم —
        # نه پیام موقتِ «در حال پردازش» (که «پاسخ حاوی» توش نیست) و نه
        # تلاش دومِ fallback (که parse_mode=None داره).
        if "پاسخ حاوی" in text and kwargs.get("parse_mode") is not None:
            raise BadRequest("Can't parse entities: bad markdown")
        return await real_send_message(chat_id, text, **kwargs)

    bot.send_message = flaky_send_message

    await ai_assistant.ask_command(update, context)

    matching = [m for m in sent_messages if "پاسخ حاوی" in m[1]]
    assert len(matching) == 1
    assert matching[0][2] is None  # دومین تلاش با parse_mode=None (متن ساده) بود
