# tests/test_app_routing.py
#
# این تست‌ها تضمین می‌کنند که هر دکمه‌ی واقعاً رندرشده در یک کیبورد، دقیقاً
# یک هندلر در app._BUTTON_HANDLERS دارد — به‌خصوص دو دکمه‌ی «بازگشت» که
# متن‌شان فقط در یک فاصله فرق دارد.

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import app  # noqa: E402
from bme_bot.handlers import admin  # noqa: E402
from bme_bot.keyboards import reply_keyboards  # noqa: E402


def _all_rendered_button_texts():
    """تمام متن‌هایی که واقعاً در یکی از کیبوردهای ریپلای رندر می‌شوند."""
    texts = set()
    for keyboard in (
        reply_keyboards.MAIN_MENU_BUTTONS,
        reply_keyboards.EDUCATION_MENU_BUTTONS,
        reply_keyboards.SENSORS_COMPONENTS_MENU_BUTTONS,
        reply_keyboards.TOOLS_MENU_BUTTONS,
    ):
        for row in keyboard:
            for btn in row:
                texts.add(btn.text)
    return texts


def test_every_rendered_button_has_a_handler():
    rendered = _all_rendered_button_texts()
    missing = rendered - set(app._BUTTON_HANDLERS.keys())
    assert not missing, f"این دکمه‌ها رندر می‌شوند ولی در _BUTTON_HANDLERS هندلر ندارند: {missing}"


def test_the_two_back_buttons_are_distinct_strings():
    """اگر این دو رشته یک روز به اشتباه یکسان شوند (مثلاً فاصله‌ی حیاتی حذف
    شود)، این تست بلافاصله fail می‌شود."""
    assert reply_keyboards.BACK_TO_MAIN_TEXT != reply_keyboards.BACK_TO_EDUCATION_TEXT


def test_back_buttons_route_to_correct_distinct_handlers():
    main_handler = app._BUTTON_HANDLERS[reply_keyboards.BACK_TO_MAIN_TEXT]
    education_handler = app._BUTTON_HANDLERS[reply_keyboards.BACK_TO_EDUCATION_TEXT]

    assert main_handler is not education_handler
    assert main_handler.__name__ == "handle_back_to_main"
    assert education_handler.__name__ == "handle_back_to_education"


# ============================== _post_init: زمان‌بندی خلاصه‌ی روزانه ==============================

def test_button_handlers_has_no_orphaned_keys():
    """همه‌ی کلیدهای _BUTTON_HANDLERS باید واقعاً در یک کیبورد رندر شوند —
    هیچ کلید یتیمی مجاز نیست."""
    rendered = _all_rendered_button_texts()
    orphaned = set(app._BUTTON_HANDLERS.keys()) - rendered
    assert not orphaned, f"کلیدهای غیرمنتظره در _BUTTON_HANDLERS: {orphaned}"


@pytest.mark.asyncio
async def test_post_init_schedules_daily_summary_job(monkeypatch):
    """بند ۱.۱-ج: _post_init باید send_daily_summary را روی job_queue واقعی
    application با run_daily ثبت کند — مطمئن شدن از این‌که این «سیم‌کشی» به
    سادگی فراموش/جابه‌جا نشده، نه این‌که خودِ زمان‌بندی واقعی JobQueue را
    دوباره تست کند (آن رفتار مال خودِ PTB است)."""
    monkeypatch.setattr(app, "setup_users_database", AsyncMock())

    run_daily_mock = Mock()
    fake_application = SimpleNamespace(job_queue=SimpleNamespace(run_daily=run_daily_mock))

    await app._post_init(fake_application)

    run_daily_mock.assert_called_once()
    args, kwargs = run_daily_mock.call_args
    assert args[0] is admin.send_daily_summary
    assert kwargs["time"].hour == 9
    assert str(kwargs["time"].tzinfo) == "Asia/Tehran"
