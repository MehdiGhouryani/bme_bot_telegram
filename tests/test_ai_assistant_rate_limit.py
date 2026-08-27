# tests/test_ai_assistant_rate_limit.py
#
# رگرسیون: دستور /ask باید هم ai_usage_repository.check_ai_limit/increment_ai_usage
# را صدا بزند — یعنی محدودیت ۱۰ سوال/روز + کول‌داون ۶۰ثانیه‌ای (که مسیر دکمه
# اعمالش می‌کند) از این مسیر هم قابل‌دورزدن نباشد. این فایل عمداً محدود و
# متمرکز است (تست پوشش جامع برای همه‌ی هندلرهای بی‌تست فعلاً در اولویت
# نیست) — فقط دقیقاً همین رگرسیون را پوشش می‌دهد، نه کل جریان
# ask_command/ai_command.
#
# منطق repository (check_ai_limit/record_attempt/increment_ai_usage) خودش در
# test_ai_usage_repository.py با دیتابیس واقعی تست شده؛ اینجا فقط «سیم‌کشی»
# هندلر به آن منطق را با mock بررسی می‌کنیم.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.constants import ChatType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import config  # noqa: E402
from bme_bot.db import ai_usage_repository  # noqa: E402
from bme_bot.handlers import ai_assistant  # noqa: E402
from bme_bot.services import ai_service  # noqa: E402
from bme_bot.utils import draft_stream  # noqa: E402


@pytest.fixture(autouse=True)
def _fast_stream_preview(monkeypatch):
    # این فایل رفتار stream_preview رو تست نمی‌کنه (رجوع به
    # test_ai_assistant_streaming.py) — فقط جلوی کند شدن کاذب تست‌ها به
    # خاطر مکث واقعی ۰.۴ثانیه‌ای هر گام رو می‌گیره.
    monkeypatch.setattr(draft_stream, "_STEP_DELAY_SECONDS", 0)


def _fake_update_and_context(question_text="یک سوال آزمایشی"):
    sent_messages = []

    class FakeBot:
        async def send_message(self, chat_id, text, **kwargs):
            sent_messages.append((chat_id, text))
            # این fixture باید یک آبجکت پیام واقعی‌نما برگرداند (نه None) —
            # ask_user_question (شاخه‌های AIResponseEmpty/AIServiceUnavailable)
            # به processing_message.message_id نیاز دارد؛ بدون آن یک
            # AttributeError پنهان می‌دهد که فقط چون outer except بی‌سروصدا
            # می‌قاپدش دیده نمی‌شود.
            return SimpleNamespace(message_id=1)

        async def delete_message(self, chat_id, message_id):
            pass

        async def do_api_request(self, endpoint, data=None, **kwargs):
            # برای stream_preview (utils/draft_stream.py) — این فایل عمداً
            # پوشش رفتار استریم رو نمی‌ده (رجوع به test_ai_assistant_streaming.py)،
            # فقط لازمه که وجود داشته باشه تا AttributeError کاذب نگیریم.
            return True

    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=555, type=ChatType.PRIVATE),
        effective_user=SimpleNamespace(id=4242),
    )
    context = SimpleNamespace(bot=FakeBot(), args=question_text.split())
    return update, context, sent_messages


@pytest.mark.asyncio
async def test_ask_command_is_rejected_when_daily_limit_reached(monkeypatch):
    """قلب رگرسیون: /ask دیگر نباید از محدودیت روزانه عبور کند."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    update, context, sent_messages = _fake_update_and_context()

    monkeypatch.setattr(
        ai_usage_repository, "check_ai_limit",
        AsyncMock(return_value=(False, "شما از تمام 10 درخواست روزانه خود استفاده کرده‌اید.")),
    )
    ask_mock = AsyncMock(side_effect=AssertionError("ai_service.ask نباید صدا زده شود"))
    monkeypatch.setattr(ai_service, "ask", ask_mock)

    await ai_assistant.ask_command(update, context)

    ask_mock.assert_not_called()
    assert any("درخواست روزانه" in text for _, text in sent_messages)


@pytest.mark.asyncio
async def test_ask_command_records_attempt_but_not_success_on_ai_failure(monkeypatch):
    """تلاش (برای کول‌داون) باید حتی روی شکست AI ثبت شود، ولی سهمیه‌ی روزانه
    (increment_ai_usage) فقط باید با پاسخ *موفق* کم شود."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    update, context, _ = _fake_update_and_context()

    monkeypatch.setattr(ai_usage_repository, "check_ai_limit", AsyncMock(return_value=(True, "OK")))
    record_attempt_mock = AsyncMock()
    increment_mock = AsyncMock()
    monkeypatch.setattr(ai_usage_repository, "record_attempt", record_attempt_mock)
    monkeypatch.setattr(ai_usage_repository, "increment_ai_usage", increment_mock)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIResponseEmpty()))

    await ai_assistant.ask_command(update, context)

    record_attempt_mock.assert_called_once_with(4242)
    increment_mock.assert_not_called()


@pytest.mark.asyncio
async def test_ask_command_increments_usage_only_after_successful_response(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    update, context, _ = _fake_update_and_context()

    monkeypatch.setattr(ai_usage_repository, "check_ai_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(ai_usage_repository, "record_attempt", AsyncMock())
    increment_mock = AsyncMock()
    monkeypatch.setattr(ai_usage_repository, "increment_ai_usage", increment_mock)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("پاسخ موفق آزمایشی", "gemini/gemini-2.5-flash")))

    await ai_assistant.ask_command(update, context)

    increment_mock.assert_called_once_with(4242)


@pytest.mark.asyncio
async def test_ask_command_logs_feature_usage_only_on_success(monkeypatch):
    """آمار پنل ادمین فقط با پاسخ موفق ثبت شود، نه با تلاش ناموفق —
    هم‌راستا با اصل «سهمیه فقط با موفقیت کم شود»."""
    from bme_bot.db import feature_usage_repository

    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(ai_usage_repository, "check_ai_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(ai_usage_repository, "record_attempt", AsyncMock())
    monkeypatch.setattr(ai_usage_repository, "increment_ai_usage", AsyncMock())
    log_usage_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_usage_mock)

    # حالت شکست: نباید ثبت شود
    update, context, _ = _fake_update_and_context()
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIResponseEmpty()))
    await ai_assistant.ask_command(update, context)
    log_usage_mock.assert_not_called()

    # حالت موفق: باید ثبت شود، این‌بار همراه با detail=مدلی که پاسخ داد
    # همراه با detail=مدلی که پاسخ داد
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("پاسخ موفق", "groq/some-model")))
    await ai_assistant.ask_command(update, context)
    log_usage_mock.assert_awaited_once_with(4242, "ai", detail="groq/some-model")


@pytest.mark.asyncio
async def test_ask_command_alerts_admins_when_ai_service_unavailable(monkeypatch):
    """AIServiceUnavailable («کلید API تنظیم نشده») باید هم به کاربر پیام
    بدهد هم ادمین را باخبر کند. مدار این فایل عمداً محدود می‌ماند."""
    from bme_bot.utils import error_reporting

    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(ai_usage_repository, "check_ai_limit", AsyncMock(return_value=(True, "OK")))
    monkeypatch.setattr(ai_usage_repository, "record_attempt", AsyncMock())
    report_issue_mock = AsyncMock()
    monkeypatch.setattr(error_reporting, "report_service_issue", report_issue_mock)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(side_effect=ai_service.AIServiceUnavailable()))

    update, context, _ = _fake_update_and_context()
    await ai_assistant.ask_command(update, context)

    report_issue_mock.assert_awaited_once()
    _, kwargs = report_issue_mock.call_args
    assert kwargs["failure_feature"] == "ai"
    assert kwargs["user_id"] == 4242


# --- معافیت کامل ادمین (همون مدار محدود این فایل، فقط برای /ask) ---

@pytest.mark.asyncio
async def test_admin_skips_limit_check_entirely(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    # ai_assistant.py با `from ..utils.admin import is_admin` وارد شده - باید
    # همین نام bind‌شده تو خودِ ماژول patch بشه، نه admin_utils.is_admin.
    monkeypatch.setattr(ai_assistant, "is_admin", lambda user_id: True)
    check_mock = AsyncMock(side_effect=AssertionError("ادمین نباید اصلاً چک بشه"))
    monkeypatch.setattr(ai_usage_repository, "check_ai_limit", check_mock)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("پاسخ", "gemini/gemini-2.5-flash")))

    update, context, _ = _fake_update_and_context()
    await ai_assistant.ask_command(update, context)

    check_mock.assert_not_called()


@pytest.mark.asyncio
async def test_admin_does_not_consume_usage_quota(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key-for-test")
    monkeypatch.setattr(ai_assistant, "is_admin", lambda user_id: True)
    record_attempt_mock = AsyncMock()
    increment_mock = AsyncMock()
    monkeypatch.setattr(ai_usage_repository, "record_attempt", record_attempt_mock)
    monkeypatch.setattr(ai_usage_repository, "increment_ai_usage", increment_mock)
    monkeypatch.setattr(ai_service, "ask", AsyncMock(return_value=("پاسخ", "gemini/gemini-2.5-flash")))

    update, context, _ = _fake_update_and_context()
    await ai_assistant.ask_command(update, context)

    record_attempt_mock.assert_not_called()
    increment_mock.assert_not_called()
