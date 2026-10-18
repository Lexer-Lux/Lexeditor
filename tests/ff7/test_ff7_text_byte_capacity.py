"""Fixed FF7 text fields serve the encoded-byte capacity the save enforces."""
import hashlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from plugins.ff7 import ai, battle, extended as ex, format_codec as codec, kernel_extra
from tests.ff7.verify_ff7_extended import exe_fixture


def test_fixed_text_fields_serve_usable_encoded_capacity():
    assert battle.ENEMY_FIELDS[0]["byteCapacity"] == 31
    assert battle.ATTACK_FIELDS[0]["byteCapacity"] == 31
    assert ex.RECRUIT_FIELDS[0]["byteCapacity"] == 11
    assert ex.DEFAULT_NAME_FIELDS[0]["byteCapacity"] == 11
    assert kernel_extra.NAME_FIELDS[0]["byteCapacity"] == 11


def test_section_buffered_text_fields_serve_no_per_field_capacity():
    placeholders = (ex.KEY_ITEM_FIELDS + ex.EXE_TEXT_FIELDS
                    + ex.FAMILIES["text"]["categories"]["texts"]["fields"])
    assert placeholders
    for field in placeholders:
        assert "byteCapacity" not in field
    for field in ai.metadata():
        assert "byteCapacity" not in field


def test_exe_text_rows_serve_per_record_capacity():
    source = exe_fixture()
    sha = hashlib.sha1(source).hexdigest().upper()
    with patch.dict(ex.EXE_PROFILES, {sha: 0x400}):
        rows = ex.ShopExecutable(source, source).records("exeText")
    assert len(rows) == len(ex.EXE_TEXT_RECORDS) > 0
    assert len({row["byteCapacity"] for row in rows}) > 1
    for row, spec in zip(rows, ex.EXE_TEXT_RECORDS):
        assert row["byteCapacity"] == spec["size"] - 1 > 0


def test_capacity_matches_save_enforcement_for_fixed_fields():
    field = battle.ENEMY_FIELDS[0]
    capacity = field["byteCapacity"]
    raw = codec.encode_text("").ljust(field["size"], b"\xff")
    fitting = "A" * capacity
    assert len(codec.encode_text(fitting)) - 1 == capacity
    battle.write_values(raw, [field], {"name": fitting})
    with pytest.raises(ValueError, match="encoded bytes"):
        battle.write_values(raw, [field], {"name": "A" * (capacity + 1)})
    # A four-character escape is one encoded byte: characters != bytes.
    escaped = "\\x41" * capacity
    assert len(escaped) == 4 * capacity
    battle.write_values(raw, [field], {"name": escaped})


def test_capacity_matches_exe_text_enforcement():
    spec = ex.EXE_TEXT_RECORDS[0]
    raw = codec.encode_text("X").ljust(spec["size"], b"\xff")
    fitting = "B" * (spec["size"] - 1)
    assert len(codec.encode_text(fitting)) - 1 == spec["size"] - 1
    ex.write_exe_text(raw, fitting)
    with pytest.raises(ValueError, match="encoded bytes"):
        ex.write_exe_text(raw, "B" * spec["size"])
