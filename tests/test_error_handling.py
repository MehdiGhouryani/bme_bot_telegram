# tests/test_error_handling.py
#
# تست‌های error handler سراسری + رفع همراهش در membership.py: قبلاً
# try/except دور بررسی عضویت به‌اشتباه کل اجرای هندلر اصلی را هم می‌گرفت،
# یعنی خطای واقعی هندلر هرگز به error handler سراسری نمی‌رسید و به‌جایش
# پیام گمراه‌کننده‌ی «خطا در بررسی عضویت» نشان داده می‌شد.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from telegram import Update  # noqa: E402

from bme_bot import app, config  # noqa: E402
from bme_bot.db import feature_usage_repository  # noqa: E402
from bme_bot.handlers import membership  # noqa: E402
from bme_bot.utils import error_reporting  # noqa: E402


def _fake_update(*, callback_query=None, message_text=None, chat_id=111):
    """یک آبجکت که isinstance(x, telegram.Update) برایش True می‌شود (با
    Mock(spec=Update))، به‌همراه فقط همان attributeهایی که global_error_handler
    واقعاً به آن‌ها نگاه می‌کند."""
    update = Mock(spec=Update)
    update.callback_query = callback_query
    update.effective_message = SimpleNamespace(text=message_text) if message_text else None
    update.effective_chat = SimpleNamespace(id=chat_id) if chat_id else None
    return update


class FakeBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent_messages.append((chat_id, text))


class FakeQuery:
    def __init__(self, data="some_callback_data"):
        self.data = data
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))


# --- error_reporting / global_error_handler ---

@pytest.mark.asyncio
async def test_global_error_handler_notifies_admins_and_user_for_message_update(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    bot = FakeBot()

    update = _fake_update(message_text="یک پیام که باعث خطا شد", chat_id=111)
    context = SimpleNamespace(bot=bot, error=RuntimeError("boom"))

    await app.global_error_handler(update, context)

    admin_msgs = [m for c, m in bot.sent_messages if c == "999"]
    user_msgs = [m for c, m in bot.sent_messages if c == 111]
    assert admin_msgs and "boom" in admin_msgs[0]
    assert user_msgs and "خطایی رخ داد" in user_msgs[0]


@pytest.mark.asyncio
async def test_global_error_handler_uses_alert_for_callback_query_updates(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    bot = FakeBot()
    query = FakeQuery()

    update = _fake_update(callback_query=query, chat_id=111)
    context = SimpleNamespace(bot=bot, error=RuntimeError("boom in callback"))

    await app.global_error_handler(update, context)

    assert query.answers and query.answers[0][1] is True  # show_alert=True
    # برای callback_query نباید پیام متنی جداگانه هم به کاربر فرستاده شود
    assert not any(c == 111 for c, _ in bot.sent_messages)


@pytest.mark.asyncio
async def test_global_error_handler_does_not_crash_if_user_notification_fails(monkeypatch):
    """اگر ارسال پیام به کاربر هم خطا بدهد، خودِ error handler نباید بترکد."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])

    class FailingBot(FakeBot):
        async def send_message(self, chat_id, text, parse_mode=None):
            if chat_id == 111:
                raise RuntimeError("cannot reach user")
            await super().send_message(chat_id, text, parse_mode)

    bot = FailingBot()
    update = _fake_update(message_text="hi", chat_id=111)
    context = SimpleNamespace(bot=bot, error=RuntimeError("original error"))

    await app.global_error_handler(update, context)  # نباید استثنایی بیندازد
    # با این حال گزارش ادمین باید موفق شده باشد
    assert any(c == "999" for c, _ in bot.sent_messages)


# --- error_reporting: throttle + لاگ ماندگار ---

@pytest.mark.asyncio
async def test_report_error_logs_persistent_failure_when_feature_given(monkeypatch):
    """وقتی failure_feature داده شود، یک رویداد در feature_usage
    ثبت شود — منبع خام «سلامت سیستم»/خلاصه‌ی روزانه."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    log_usage_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_usage_mock)
    context = SimpleNamespace(bot=FakeBot())

    await error_reporting.report_error(
        context, RuntimeError("boom"), context_label="ocr", failure_feature="ocr", user_id=42,
    )

    log_usage_mock.assert_awaited_once_with(42, "ocr_failure", detail="RuntimeError")


@pytest.mark.asyncio
async def test_report_error_skips_persistent_failure_without_feature(monkeypatch):
    """فراخوان‌های قدیمی (مثل error handler سراسری) failure_feature نمی‌دهند
    — نباید هیچ رویدادی ثبت شود (نه این‌که با user_id=None خطا بدهد)."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    log_usage_mock = AsyncMock()
    monkeypatch.setattr(feature_usage_repository, "log_usage", log_usage_mock)
    context = SimpleNamespace(bot=FakeBot())

    await error_reporting.report_error(context, RuntimeError("boom"), context_label="جایی")

    log_usage_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_error_throttles_repeated_alerts_in_same_window(monkeypatch):
    """بند ۱.۱-ب: دومین رخداد همان (context_label, نوع خطا) در همان پنجره
    نباید پیام تلگرام دوم بفرستد — فقط اولین رخداد پیام کامل می‌فرستد.

    عمداً time.monotonic سراسری mock نمی‌شود — خودِ asyncio هم داخلی از آن
    برای زمان‌بندی استفاده می‌کند؛ patch سراسری‌اش باعث StopIteration در
    کدهای داخلی event loop می‌شود. به‌جایش مستقیماً _last_alert_at را با یک
    مقدار «همین چند لحظه پیش» seed می‌کنیم — دقیقاً همان چیزی که یک رخداد
    واقعی و اخیر در آن دیکشنری می‌گذارد."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    await error_reporting.report_error(context, RuntimeError("اول"), context_label="ocr")
    await error_reporting.report_error(context, RuntimeError("دوم"), context_label="ocr")

    admin_msgs = [m for c, m in bot.sent_messages if c == "999"]
    assert len(admin_msgs) == 1
    assert "اول" in admin_msgs[0]


@pytest.mark.asyncio
async def test_report_error_sends_again_after_throttle_window_elapses(monkeypatch):
    """بعد از عبور از _ALERT_THROTTLE_SECONDS، رخداد بعدی دوباره پیام کامل
    می‌فرستد — throttle فقط داخل یک پنجره اثر دارد، نه برای همیشه."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    key = "ocr|RuntimeError"
    # وانمود می‌کنیم آخرین هشدار خیلی بیشتر از پنجره پیش بوده — بدون دست‌زدن
    # به خودِ time.monotonic سراسری (توضیح در تست بالا).
    error_reporting._last_alert_at[key] = error_reporting.time.monotonic() - error_reporting._ALERT_THROTTLE_SECONDS - 1

    await error_reporting.report_error(context, RuntimeError("دوم"), context_label="ocr")

    admin_msgs = [m for c, m in bot.sent_messages if c == "999"]
    assert len(admin_msgs) == 1
    assert "دوم" in admin_msgs[0]


@pytest.mark.asyncio
async def test_report_error_different_labels_do_not_share_throttle(monkeypatch):
    """کلید throttle باید شامل context_label باشد — شکست AI نباید شکست OCR
    را throttle کند (دو مشکل کاملاً جدا هستند)."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    await error_reporting.report_error(context, RuntimeError("مشکل AI"), context_label="/ask")
    await error_reporting.report_error(context, RuntimeError("مشکل OCR"), context_label="ocr")

    admin_msgs = [m for c, m in bot.sent_messages if c == "999"]
    assert len(admin_msgs) == 2


@pytest.mark.asyncio
async def test_report_service_issue_sends_lightweight_message_without_traceback(monkeypatch):
    """report_service_issue برای خطاهای شناخته‌شده است — نباید بخش
    Traceback را داشته باشد (برخلاف report_error)."""
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    await error_reporting.report_service_issue(
        context, "هیچ کلید OCR تنظیم نشده", context_label="ocr",
    )

    admin_msgs = [m for c, m in bot.sent_messages if c == "999"]
    assert len(admin_msgs) == 1
    assert "Traceback" not in admin_msgs[0]
    assert "هیچ کلید OCR تنظیم نشده" in admin_msgs[0]


@pytest.mark.asyncio
async def test_report_service_issue_also_throttles(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["999"])
    bot = FakeBot()
    context = SimpleNamespace(bot=bot)

    await error_reporting.report_service_issue(context, "پیام یکسان", context_label="ocr")
    await error_reporting.report_service_issue(context, "پیام یکسان", context_label="ocr")

    admin_msgs = [m for c, m in bot.sent_messages if c == "999"]
    assert len(admin_msgs) == 1


# --- membership_required try/except scope fix ---

@pytest.mark.asyncio
async def test_membership_required_lets_handler_errors_propagate(monkeypatch):
    """رفع همراه یافته‌ی ۱۰: اگر هندلر اصلی (نه بررسی عضویت) خطا بدهد، آن خطا
    باید بالا برود (تا error handler سراسری بگیرد)، نه اینکه به‌اشتباه به‌عنوان
    «خطای بررسی عضویت» قورت داده شود."""

    async def failing_handler(update, context):
        raise ValueError("این خطای واقعی هندلر است، نه خطای بررسی عضویت")

    wrapped = membership.membership_required(failing_handler)

    class FakeBotWithMembership:
        async def get_chat_member(self, chat_id, user_id):
            return SimpleNamespace(status="member")

        async def send_message(self, chat_id, text, **kwargs):
            pass

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        callback_query=None,
        message=SimpleNamespace(reply_text=lambda *a, **k: None),
    )
    context = SimpleNamespace(bot=FakeBotWithMembership(), user_data={})

    with pytest.raises(ValueError, match="این خطای واقعی هندلر است"):
        await wrapped(update, context)


@pytest.mark.asyncio
async def test_membership_required_still_handles_membership_check_failure_gracefully(monkeypatch):
    """محافظت اصلی (خطای واقعیِ بررسی عضویت) باید دست‌نخورده بماند."""

    async def handler_that_should_not_run(update, context):
        raise AssertionError("این هندلر نباید اصلاً اجرا شود")

    wrapped = membership.membership_required(handler_that_should_not_run)

    class FailingMembershipBot:
        async def get_chat_member(self, chat_id, user_id):
            raise RuntimeError("Telegram API is down")

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42),
        callback_query=None,
        message=SimpleNamespace(replies=[]),
    )

    async def reply_text(text, **kwargs):
        update.message.replies.append(text)

    update.message.reply_text = reply_text
    context = SimpleNamespace(bot=FailingMembershipBot(), user_data={})

    await wrapped(update, context)  # نباید RuntimeError را بالا بفرستد

    assert update.message.replies == ["خطا در بررسی عضویت. لطفاً لحظاتی دیگر دوباره تلاش کنید."]
