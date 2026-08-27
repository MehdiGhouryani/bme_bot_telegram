# tests/test_handler_registration.py
#
# تست‌های handlerها معمولاً هر تابع را *مستقیم* صدا می‌زنند (مثلاً
# `await admin.toggle_ban(update, context)`) — یعنی لایه‌ی واقعی
# تشخیص/دیسپچ PTB (ترتیب ثبت handlerها، pattern matching واقعی
# CallbackQueryHandler/ConversationHandler) هیچ‌جای دیگری به‌طور مستقیم
# تست نمی‌شود. این فایل دقیقاً همان چیزی را می‌سازد که app.main() واقعاً
# می‌سازد (بدون polling/شبکه‌ی واقعی) و بررسی می‌کند یک update واقعی به کدام
# handler می‌رسد — نه با فراخوانی مستقیم تابع، با check_update واقعی PTB.
#
# چرا این مهم است: باگ ترتیب ثبت (مثل تداخل admin_edit_field با
# decode_device_action عمومی، مستند در equipment_admin_edit.py) دقیقاً از
# نوع باگی است که تست‌های واحد معمولی هرگز نمی‌گیرند — چون هرکدام فقط یک
# تابع را مستقیم صدا می‌زنند، نه از طریق دیسپچر واقعی.

import datetime
import sys
from pathlib import Path

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot import app, config  # noqa: E402


@pytest.fixture
def built_app(monkeypatch):
    """دقیقاً همان چیزی که app.main() می‌سازد — با token جعلی و run_polling
    غیرفعال (بدون این‌ها نمی‌شود بدون شبکه‌ی واقعی/توکن واقعی اجرا کرد)."""
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123456789:AAFakeTokenForRegistrationTestOnly")
    monkeypatch.setattr(config, "ADMIN_CHAT_ID", ["42"])

    captured = {}

    def fake_run_polling(self, *a, **kw):
        captured["app"] = self

    monkeypatch.setattr(app.Application, "run_polling", fake_run_polling)
    app.main()
    return captured["app"]


def _make_callback_update(data, user_id=42, chat_id=42):
    """یک callback query واقعی همیشه یک message واقعی دارد (همان پیامی که
    دکمه رویش بود) — بدون message، ConversationHandler.check_update نمی‌تواند
    effective_chat را resolve کند و همیشه False برمی‌گرداند (نه یک تست معتبر)."""
    user = User(id=user_id, is_bot=False, first_name="Test")
    chat = Chat(id=chat_id, type="private")
    message = Message(message_id=555, date=datetime.datetime.now(), chat=chat, from_user=user)
    query = CallbackQuery(id="1", from_user=user, chat_instance="x", data=data, message=message)
    return Update(update_id=1, callback_query=query)


def _first_matching_handler_name(built_app, update, group=0):
    """همان منطق دیسپچ PTB (بدون نیاز به initialize()/شبکه): اولین handler
    که check_update واقعی‌اش True برمی‌گرداند."""
    for handler in built_app.handlers[group]:
        if handler.check_update(update):
            return getattr(handler, "name", None) or type(handler).__name__
    return None


@pytest.mark.parametrize(
    "callback_data, expected_handler_name",
    [
        # باید equipment_field_edit را بگیرد، نه CallbackQueryHandler
        # عمومی (که یعنی equipment_callbacks.route/decode_device_action
        # اشتباهاً آن را به‌عنوان یک کلیک روی device:action:line می‌گرفت).
        ("admin_edit_field:xray:structure:imaging_devices", "equipment_field_edit"),
        # یک کلیک عادی روی دستگاه باید همچنان به دیسپچر عمومی برسد.
        ("xray:structure:imaging_devices", "CallbackQueryHandler"),
        # ورودی دو ConversationHandler موجود admin.py.
        ("admin_users_search_start", "admin_user_search"),
        ("admin_menu:broadcast", "admin_broadcast"),
        # admin_menu:health هیچ ConversationHandler ای ندارد — باید به
        # دیسپچر عمومی برسد.
        ("admin_menu:health", "CallbackQueryHandler"),
        # فاز M1 (تعمیرات و نگهداری): باید maintenance_admin_edit را بگیرد،
        # نه دیسپچر عمومی (همان کلاس باگی که admin_edit_field بالا برایش
        # تست دارد).
        ("maint_admin_open:xray", "maintenance_admin_edit"),
        # فاز M2 (نمایش کاربر عادی): stateless است، ConversationHandler
        # ندارد — باید به دیسپچر عمومی برسد (که خودش data.startswith
        # ("maint_view_") را داخل app.callback_handler چک می‌کند).
        ("maint_view_open:xray", "CallbackQueryHandler"),
    ],
)
def test_callback_routes_to_expected_handler(built_app, callback_data, expected_handler_name):
    update = _make_callback_update(callback_data)
    assert _first_matching_handler_name(built_app, update) == expected_handler_name


def test_group_0_registration_order_matches_documented_requirement():
    """هر پنج ConversationHandler (admin.py ×۳ + equipment_admin_edit ×۱ +
    maintenance_admin_edit ×۱) باید *قبل* از CallbackQueryHandler عمومی ثبت
    شده باشند — این خودِ الزامی است که در سربرگ‌های admin.py/
    equipment_admin_edit.py/maintenance_admin_edit.py/app.py مستند شده؛ این
    تست تضمین می‌کند یک refactor آینده این ترتیب را خراب نکند.

    پنج ConversationHandler همین الان ثبت شده‌اند: admin.py ×۳
    (user_search/broadcast/limits_edit) + equipment_admin_edit ×۱ +
    maintenance_admin_edit ×۱. اگر یک ConversationHandler جدید اضافه شد،
    این عدد باید همراهش به‌روز شود."""
    from telegram.ext import CallbackQueryHandler, ConversationHandler

    monkeypatch_token = "123456789:AAFakeTokenForRegistrationTestOnly"
    original_token = config.TELEGRAM_BOT_TOKEN
    original_admin = config.ADMIN_CHAT_ID
    config.TELEGRAM_BOT_TOKEN = monkeypatch_token
    config.ADMIN_CHAT_ID = ["42"]
    captured = {}
    original_run_polling = app.Application.run_polling
    app.Application.run_polling = lambda self, *a, **kw: captured.__setitem__("app", self)
    try:
        app.main()
        built = captured["app"]
        group0 = built.handlers[0]
        conversation_indices = [i for i, h in enumerate(group0) if isinstance(h, ConversationHandler)]
        generic_callback_indices = [
            i for i, h in enumerate(group0)
            if isinstance(h, CallbackQueryHandler) and not isinstance(h, ConversationHandler)
        ]
        assert len(conversation_indices) == 5
        assert len(generic_callback_indices) == 1
        assert max(conversation_indices) < generic_callback_indices[0]
    finally:
        app.Application.run_polling = original_run_polling
        config.TELEGRAM_BOT_TOKEN = original_token
        config.ADMIN_CHAT_ID = original_admin
