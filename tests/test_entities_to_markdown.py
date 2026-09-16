# tests/test_entities_to_markdown.py

import sys
from pathlib import Path

from telegram import MessageEntity

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bme_bot.utils.entities_to_markdown import (  # noqa: E402
    FLAVOR_LEGACY,
    FLAVOR_RICH,
    entities_to_markdown,
)


def _entity(type_, offset, length):
    return MessageEntity(type=type_, offset=offset, length=length)


# --- بدون entity: متن دست‌نخورده (شامل ##/- دستی) ---

def test_no_entities_returns_text_unchanged():
    text = "## تیتر\n- بولت اول\n- بولت دوم"
    assert entities_to_markdown(text, None) == text
    assert entities_to_markdown(text, []) == text


def test_none_and_empty_text_are_safe():
    assert entities_to_markdown(None, None) == ""
    assert entities_to_markdown("", []) == ""


# --- بولد/ایتالیک/کد — فلیور rich (دو-ستاره برای بولد) ---

def test_rich_bold_entity_reconstructed_as_double_star():
    text = "متن مهم است"
    entities = [_entity(MessageEntity.BOLD, 0, len("متن"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_RICH)

    assert result == "**متن** مهم است"


def test_rich_italic_entity_reconstructed_as_single_star():
    text = "کلمه توضیح"
    entities = [_entity(MessageEntity.ITALIC, 0, len("کلمه"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_RICH)

    assert result == "*کلمه* توضیح"


def test_rich_code_entity_reconstructed_as_backtick():
    text = "مقدار x=5 است"
    entities = [_entity(MessageEntity.CODE, len("مقدار "), len("x=5"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_RICH)

    assert result == "مقدار `x=5` است"


def test_rich_strikethrough_entity_reconstructed_as_double_tilde():
    text = "قدیمی حذف شد"
    entities = [_entity(MessageEntity.STRIKETHROUGH, 0, len("قدیمی"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_RICH)

    assert result == "~~قدیمی~~ حذف شد"


def test_manual_headers_and_bullets_survive_alongside_reconstructed_bold():
    """این دقیقاً همون سناریوی واقعیه: ادمین ## رو دستی تایپ می‌کنه (بدون
    entity) ولی بولد رو از دکمه‌ی تلگرام می‌زنه (entity واقعی)."""
    text = "## کاربرد\nمتن مهم درباره‌ی دستگاه"
    entities = [_entity(MessageEntity.BOLD, len("## کاربرد\n"), len("متن مهم"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_RICH)

    assert result == "## کاربرد\n**متن مهم** درباره‌ی دستگاه"


# --- بولد/ایتالیک — فلیور legacy (تک-ستاره برای بولد، زیرخط برای ایتالیک) ---

def test_legacy_bold_entity_reconstructed_as_single_star():
    text = "متن مهم است"
    entities = [_entity(MessageEntity.BOLD, 0, len("متن"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_LEGACY)

    assert result == "*متن* مهم است"


def test_legacy_italic_entity_reconstructed_as_underscore():
    text = "کلمه توضیح"
    entities = [_entity(MessageEntity.ITALIC, 0, len("کلمه"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_LEGACY)

    assert result == "_کلمه_ توضیح"


def test_legacy_strikethrough_is_dropped_not_translated_to_invalid_syntax():
    """Markdown قدیمی (V1) اصلاً strikethrough نداره — باید بی‌صدا نادیده
    گرفته بشه (متن ساده بمونه)، نه سینتکس نامعتبر تزریق بشه."""
    text = "قدیمی حذف شد"
    entities = [_entity(MessageEntity.STRIKETHROUGH, 0, len("قدیمی"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_LEGACY)

    assert result == text


# --- ایموجی خارج از BMP (UTF-16 offset) ---

def test_bold_entity_after_out_of_bmp_emoji_is_positioned_correctly():
    """👤 دو واحد UTF-16 می‌گیره ولی ۱ کاراکتر پایتونه — entity.offset بعد
    از این ایموجی باید درست به کاراکتر پایتونیِ بعدش نگاشت بشه، نه یکی
    جابه‌جا."""
    text = "👤 متن بولد بعدش"
    bold_word = "متن"
    # آفست UTF-16: ۲ واحد برای 👤 + ۱ واحد برای فاصله = ۳
    entities = [_entity(MessageEntity.BOLD, 3, len(bold_word))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_RICH)

    assert result == "👤 **متن** بولد بعدش"


# --- entity های تو در تو ---

def test_nested_bold_inside_italic_wraps_correctly():
    text = "خیلی مهم است"
    entities = [
        _entity(MessageEntity.ITALIC, 0, len("خیلی مهم")),
        _entity(MessageEntity.BOLD, len("خیلی "), len("مهم")),
    ]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_RICH)

    assert result == "*خیلی **مهم*** است"


# --- entity هایی که این فلیور اصلاً نمی‌شناسه (مثلاً mention/hashtag خودکار) ---

def test_unmapped_entity_types_are_ignored():
    text = "@username یه پیام"
    entities = [_entity(MessageEntity.MENTION, 0, len("@username"))]

    result = entities_to_markdown(text, entities, flavor=FLAVOR_RICH)

    assert result == text
