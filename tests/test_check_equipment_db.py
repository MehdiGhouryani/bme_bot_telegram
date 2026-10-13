# tests/test_check_equipment_db.py
#
# تست tools/check_equipment_db.py — ابزار بررسی تطبیق medical_device.db با کد.

import io
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import check_equipment_db as tool  # noqa: E402

ACTIONS = {"types", "definition", "structure", "operation",
           "advantages_disadvantages", "safety", "related_technologies"}
TREE = {
    "menus": {"line": [[{"label": "الف", "id": "dev_a"}], [{"label": "ب", "id": "dev_b"}]]},
    "device_line": {"dev_a": "line", "dev_b": "line"},
}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 20
GOOD_TABLE = "| الف | ب |\n|---|---|\n| 1 | 2 |"


def _make_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE information (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, definition TEXT,
        types TEXT, structure TEXT, operation TEXT, advantages_disadvantages TEXT, safety TEXT,
        related_technologies TEXT, photo BLOB)"""
    )
    for r in rows:
        base = {"name": "dev_a", "definition": "*تعریف* ساده", "types": GOOD_TABLE, "structure": "س",
                "operation": "ع", "advantages_disadvantages": "م", "safety": "ا",
                "related_technologies": "ت", "photo": JPEG}
        base.update(r)
        conn.execute(
            "INSERT INTO information (name, definition, types, structure, operation, "
            "advantages_disadvantages, safety, related_technologies, photo) VALUES (?,?,?,?,?,?,?,?,?)",
            tuple(base[k] for k in ("name", "definition", "types", "structure", "operation",
                                    "advantages_disadvantages", "safety", "related_technologies", "photo")),
        )
    conn.commit()
    conn.close()


def _check(path):
    return tool.check_database(str(path), TREE, ACTIONS)


# --------------------------- legacy / rich helpers ---------------------------

def test_legacy_single_star_is_fine():
    assert tool.definition_legacy_problems("*بولد* و متن") == []


def test_legacy_double_star_flagged():
    assert any("**" in p for p in tool.definition_legacy_problems("**بولد** و متن"))


def test_legacy_unbalanced_star_underscore_backtick_bracket_flagged():
    assert tool.definition_legacy_problems("*باز")
    assert tool.definition_legacy_problems("snake_case")
    assert tool.definition_legacy_problems("کد `x")
    assert tool.definition_legacy_problems("[لینک")


def test_legacy_escaped_chars_not_flagged():
    assert tool.definition_legacy_problems(r"snake\_case") == []


def test_legacy_caption_length_uses_utf16():
    emoji_text = "😀" * 600  # 1200 واحد UTF-16 ولی فقط 600 کاراکتر
    assert any("سقف" in p for p in tool.definition_legacy_problems(emoji_text))


def test_rich_valid_table_and_bold_ok():
    assert tool.rich_problems("**عنوان**\n\n" + GOOD_TABLE) == []


def test_rich_table_problems_flagged():
    assert tool.rich_problems("| الف | ب |\n| 1 | 2 |")  # بدون separator
    assert tool.rich_problems("| الف | ب |\n|---|---|\n| 1 |")  # ستون ناهماهنگ
    assert tool.rich_problems("متن\n| الف | ب |\n|---|---|\n| 1 | 2 |")  # بدون خط خالی قبلش
    assert tool.rich_problems("**باز")


def test_rich_size_limit_flagged():
    assert any("بایت" in p for p in tool.rich_problems("ا" * 20000))


# --------------------------- check_database ---------------------------

def test_clean_db_has_no_errors(tmp_path):
    db = tmp_path / "m.db"
    _make_db(db, [{"name": "dev_a"}, {"name": "dev_b"}])
    result = _check(db)
    assert result["errors"] == []
    assert result["warnings"] == []


def test_missing_and_extra_rows_are_warnings_not_errors(tmp_path):
    db = tmp_path / "m.db"
    _make_db(db, [{"name": "dev_a"}, {"name": "ghost"}])
    result = _check(db)
    assert result["errors"] == []
    assert any("dev_b" in w for w in result["warnings"])
    assert any("ghost" in w for w in result["warnings"])


def test_duplicate_and_blank_names_are_errors(tmp_path):
    db = tmp_path / "m.db"
    _make_db(db, [{"name": "dev_a"}, {"name": "dev_a"}, {"name": " dev_b"}])
    errors = _check(db)["errors"]
    assert any("تکراری" in e for e in errors)
    assert any("فاصله" in e for e in errors)


def test_definition_without_photo_is_error(tmp_path):
    db = tmp_path / "m.db"
    _make_db(db, [{"name": "dev_a", "photo": None}, {"name": "dev_b"}])
    assert any("عکس ندارد" in e for e in _check(db)["errors"])


def test_bad_photo_bytes_error_and_webp_warning(tmp_path):
    db = tmp_path / "m.db"
    webp = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"0" * 10
    _make_db(db, [{"name": "dev_a", "photo": b"not an image"}, {"name": "dev_b", "photo": webp}])
    result = _check(db)
    assert any("dev_a.photo" in e for e in result["errors"])
    assert not any("dev_b.photo" in e for e in result["errors"])
    assert any("dev_b.photo" in w and "WebP" in w for w in result["warnings"])


def test_missing_column_is_reported_not_crashed(tmp_path):
    db = tmp_path / "m.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE information (id INTEGER, name TEXT, definition TEXT)")
    conn.commit()
    conn.close()
    assert any("ستون" in e for e in _check(db)["errors"])


def test_empty_field_on_reachable_device_is_warning(tmp_path):
    db = tmp_path / "m.db"
    _make_db(db, [{"name": "dev_a", "safety": ""}, {"name": "dev_b"}])
    result = _check(db)
    assert result["errors"] == []
    assert any("dev_a.safety" in w for w in result["warnings"])


# --------------------------- fix_database ---------------------------

def test_fix_converts_definition_and_webp_only_and_leaves_source_untouched(tmp_path):
    PIL = pytest.importorskip("PIL.Image")
    buf = io.BytesIO()
    PIL.new("RGB", (8, 8), "red").save(buf, format="WEBP")
    src, dst = tmp_path / "src.db", tmp_path / "dst.db"
    _make_db(src, [
        {"name": "dev_a", "definition": "**بولد** متن", "photo": buf.getvalue()},
        {"name": "dev_b"},
    ])
    before = src.read_bytes()

    changed = tool.fix_database(str(src), str(dst))

    assert changed == {"definitions": 1, "photos": 1}
    assert src.read_bytes() == before

    a = sqlite3.connect(src)
    b = sqlite3.connect(dst)
    cols = [r[1] for r in a.execute("PRAGMA table_info(information)")]
    ra = {r[0]: r for r in a.execute("SELECT * FROM information")}
    rb = {r[0]: r for r in b.execute("SELECT * FROM information")}
    a.close()
    b.close()
    changed_cols = {c for i in ra for k, c in enumerate(cols) if ra[i][k] != rb[i][k]}
    assert changed_cols == {"definition", "photo"}
    row = next(r for r in rb.values() if r[cols.index("name")] == "dev_a")
    assert row[cols.index("definition")] == "*بولد* متن"
    assert bytes(row[cols.index("photo")])[:3] == b"\xff\xd8\xff"
    assert _check(dst)["errors"] == []
