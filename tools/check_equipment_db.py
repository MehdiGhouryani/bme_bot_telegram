# tools/check_equipment_db.py
#
# بررسی تطبیق یک فایل medical_device.db با «قرارداد» واقعی کد — قبل از این‌که
# روی سرور جایگزین دیتابیس فعلی بشه. فقط می‌خونه (فایل ورودی رو تغییر نمی‌ده).
#
#   PYTHONPATH=src python tools/check_equipment_db.py path/to/medical_device.db
#   PYTHONPATH=src python tools/check_equipment_db.py in.db --fix out.db
#
# --fix یک *کپی* (out.db) می‌سازد و فقط این دو تبدیل مکانیکی را روش انجام
# می‌دهد، بعد دوباره بررسی می‌کند: (۱) ستون definition از سینتکس Rich به legacy
# (** → *)؛ (۲) عکس‌های WebP به JPEG (نیاز به Pillow). هیچ متن/ردیف دیگری
# تغییر نمی‌کند.
#
# قرارداد (از کد):
# - جدول information با ستون‌های name + همه‌ی اکشن‌های device_detail_template +
#   photo (equipment_repository). ردیف هر دستگاه با name == شناسه‌ی دستگاه در
#   data/equipment_menu.json (device_line).
# - «معرفی» (definition) به‌صورت *کپشن عکس* با ParseMode.MARKDOWN قدیمی (V1)
#   فرستاده می‌شه: بولد = یک ستاره، سقف ۱۰۲۴ واحد UTF-16، و عکس الزامی است
#   (send_photo بدون عکس شکست می‌خوره). بولد دو‌ستاره اینجا *فرمت اشتباهه*.
# - بقیه‌ی اکشن‌ها اول با Rich Markdown (سقف ۳۲۷۶۸ بایت)، و در صورت شکست با
#   Markdown قدیمی/پیام ساده (سقف ۴۰۹۶ واحد UTF-16) نشون داده می‌شن.
#
# خروجی: errors (باید قبل از استقرار رفع بشن) و warnings (آگاهی/تصمیم شما).
# کد خروج ۱ اگه error وجود داشته باشه.

import re
import sqlite3
import sys

MAX_CAPTION_UTF16 = 1024
MAX_RICH_BYTES = 32768
MAX_PLAIN_UTF16 = 4096
MAX_PHOTO_BYTES = 10 * 1024 * 1024  # سقف عکس در Bot API

_IMAGE_MAGICS = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")
_WEBP_MAGIC_PREFIX = b"RIFF"  # RIFF....WEBP
_TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|(\s*:?-{3,}:?\s*\|)+\s*$")


def _is_webp(head: bytes) -> bool:
    return head.startswith(_WEBP_MAGIC_PREFIX) and head[8:12] == b"WEBP"


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _unescaped(text: str) -> str:
    """متن بدون کاراکترهای escape‌شده با بک‌اسلش (برای شمارش نشانه‌های legacy)."""
    return re.sub(r"\\.", "", text, flags=re.DOTALL)


def definition_legacy_problems(text: str) -> list[str]:
    """مشکلاتی که یک متن «معرفی» رو برای parse_mode=MARKDOWN (V1) خراب می‌کنه."""
    problems = []
    if "**" in text:
        problems.append("بولد دو‌ستاره (**) — در Markdown قدیمی بولد یک ستاره است")
    body = _unescaped(text)
    if body.count("*") % 2:
        problems.append("تعداد * جفت نیست")
    for ch, name in (("_", "_"), ("`", "backtick"), ("[", "[")):
        if ch in body:
            problems.append(f"{name} بدون escape (در legacy باید جفت/escape بشه)")
    if _utf16_len(text) > MAX_CAPTION_UTF16:
        problems.append(f"طول {_utf16_len(text)} > {MAX_CAPTION_UTF16} (سقف کپشن)")
    return problems


def rich_problems(text: str) -> list[str]:
    """بررسی ساختاری ارزان برای Rich Markdown (نه جایگزین parse واقعی تلگرام)."""
    problems = []
    if len(text.encode("utf-8")) > MAX_RICH_BYTES:
        problems.append(f"بیش از {MAX_RICH_BYTES} بایت")
    if text.count("**") % 2:
        problems.append("تعداد ** جفت نیست")

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        if _TABLE_LINE.match(lines[i]):
            j = i
            while j < len(lines) and _TABLE_LINE.match(lines[j]):
                j += 1
            block = lines[i:j]

            def cells(line):
                return len(re.split(r"(?<!\\)\|", line.strip())[1:-1])

            if len(block) < 2 or not _TABLE_SEPARATOR.match(block[1]):
                problems.append("جدول بدون ردیف جداکننده‌ی |---|")
            if any(cells(line) != cells(block[0]) for line in block):
                problems.append("تعداد ستون‌های جدول در ردیف‌ها یکسان نیست")
            if i > 0 and lines[i - 1].strip():
                problems.append("جدول بدون خط خالی قبل از خودش")
            i = j
        else:
            i += 1
    return problems


def check_database(db_path: str, tree: dict, allowed_actions: set[str]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    info: dict = {}

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            errors.append("integrity_check دیتابیس ناموفق است")

        columns = {r[1] for r in conn.execute("PRAGMA table_info(information)")}
        needed = {"name", "photo"} | set(allowed_actions)
        if not columns:
            errors.append("جدول information وجود ندارد")
            return {"errors": errors, "warnings": warnings, "info": info}
        missing_cols = sorted(needed - columns)
        if missing_cols:
            errors.append(f"ستون(های) لازم در جدول نیست: {missing_cols}")
            return {"errors": errors, "warnings": warnings, "info": info}

        action_cols = sorted(allowed_actions)
        select = ", ".join(["id", "name", "photo", *action_cols])
        rows = [dict(zip(["id", "name", "photo", *action_cols], r))
                for r in conn.execute(f"SELECT {select} FROM information ORDER BY id")]
    finally:
        conn.close()

    info["rows"] = len(rows)
    by_name: dict[str, list[dict]] = {}
    for r in rows:
        name = r["name"]
        if not name or name != name.strip():
            errors.append(f"ردیف id={r['id']}: name خالی یا با فاصله‌ی اضافه")
            continue
        by_name.setdefault(name, []).append(r)

    for name, group in by_name.items():
        if len(group) > 1:
            errors.append(f"name تکراری '{name}' (id ها: {[g['id'] for g in group]})")

    # --- تطبیق با درخت منو ---
    menus = tree["menus"]
    device_line = tree["device_line"]
    button_ids = {b["id"] for rows_ in menus.values() for row in rows_ for b in row}
    reachable = sorted(d for d in device_line if d in button_ids)
    info["reachable_devices"] = len(reachable)

    missing = [d for d in reachable if d not in by_name]
    if missing:
        warnings.append(f"دستگاه‌های موجود در منو که ردیف ندارند ({len(missing)}): {missing}")
    extra = sorted(n for n in by_name if n not in reachable)
    if extra:
        warnings.append(f"ردیف‌هایی که در هیچ دکمه‌ی منویی نیستند ({len(extra)}): {extra}")

    # --- محتوای هر ردیف ---
    for name, group in by_name.items():
        r = group[0]
        photo = r["photo"]
        definition = r["definition"]

        if definition:
            for p in definition_legacy_problems(definition):
                errors.append(f"{name}.definition: {p}")
            if not photo:
                errors.append(f"{name}: «معرفی» دارد ولی عکس ندارد (send_photo بدون عکس شکست می‌خورد)")
        if photo:
            if not isinstance(photo, (bytes, bytearray)):
                errors.append(f"{name}.photo: BLOB نیست ({type(photo).__name__})")
            else:
                head = bytes(photo[:12])
                if _is_webp(head):
                    warnings.append(
                        f"{name}.photo: فرمت WebP است (پذیرش WebP به‌عنوان photo توسط تلگرام "
                        "تأیید نشده؛ --fix به JPEG تبدیلش می‌کند)"
                    )
                elif not head.startswith(_IMAGE_MAGICS):
                    errors.append(f"{name}.photo: فرمت JPEG/PNG معتبر نیست")
                if len(photo) > MAX_PHOTO_BYTES:
                    errors.append(f"{name}.photo: بزرگ‌تر از {MAX_PHOTO_BYTES} بایت")

        for col in action_cols:
            if col == "definition":
                continue
            text = r[col]
            if not text:
                if name in reachable:
                    warnings.append(f"{name}.{col}: خالی")
                continue
            for p in rich_problems(text):
                errors.append(f"{name}.{col}: {p}")
            if _utf16_len(text) > MAX_PLAIN_UTF16:
                warnings.append(
                    f"{name}.{col}: {_utf16_len(text)} > {MAX_PLAIN_UTF16} — اگر Rich رد شود، "
                    "مسیر جایگزین (Markdown قدیمی) نمی‌تواند نمایشش بدهد"
                )
    return {"errors": errors, "warnings": warnings, "info": info}


def _webp_to_jpeg(data: bytes) -> bytes:
    import io

    from PIL import Image  # lazy: فقط برای --fix لازم است، نه برای بررسی

    image = Image.open(io.BytesIO(data)).convert("RGB")
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95, optimize=True)
    return out.getvalue()


def fix_database(src_path: str, dest_path: str) -> dict:
    """یک *کپی* از src می‌سازد و فقط (۱) ستون definition را از سینتکس Rich به
    legacy تبدیل می‌کند (** → *) و (۲) عکس‌های WebP را به JPEG. هیچ
    ستون/ردیف دیگری تغییر نمی‌کند. تعداد تغییرها را برمی‌گرداند."""
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(dest_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    conn = sqlite3.connect(dest_path)
    changed = {"definitions": 0, "photos": 0}
    try:
        for row_id, text, photo in conn.execute("SELECT id, definition, photo FROM information").fetchall():
            if text and "**" in text:
                conn.execute("UPDATE information SET definition = ? WHERE id = ?",
                             (text.replace("**", "*"), row_id))
                changed["definitions"] += 1
            if photo and _is_webp(bytes(photo[:12])):
                conn.execute("UPDATE information SET photo = ? WHERE id = ?",
                             (_webp_to_jpeg(bytes(photo)), row_id))
                changed["photos"] += 1
        conn.commit()
    finally:
        conn.close()
    return changed


def main(argv: list[str]) -> int:
    from bme_bot import equipment_tree

    if not argv or argv[0].startswith("-"):
        print(__doc__ or "usage: check_equipment_db.py DB [--fix OUT_DB]")
        return 2
    db_path = argv[0]

    if "--fix" in argv:
        out = argv[argv.index("--fix") + 1]
        changed = fix_database(db_path, out)
        print(f"✂️  {changed['definitions']} متن «معرفی» → سینتکس legacy، "
              f"{changed['photos']} عکس WebP → JPEG  ⇒  {out}")
        db_path = out

    result = check_database(db_path, equipment_tree._load_tree(), set(equipment_tree.get_allowed_actions()))
    print(f"ردیف‌ها: {result['info'].get('rows')} | دستگاه‌های قابل‌دسترس در منو: "
          f"{result['info'].get('reachable_devices')}")
    for w in result["warnings"]:
        print("⚠️ ", w)
    for e in result["errors"]:
        print("❌", e)
    print("✅ بدون error" if not result["errors"] else f"❌ {len(result['errors'])} error")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
