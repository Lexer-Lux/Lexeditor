"""Synthetic composition checks; not evidence of retail mod compatibility."""
from hashlib import sha256
from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ds1_fixture import make_archive
from plugins.ds1.composition import Cell, compose, CompositionError, ConflictError
from plugins.ds1.formats import ItemDocument, inflate
from plugins.ds3.formats import write_field


def changed(raw, *, table="EquipParamGoods", row_id=100, field="sellValue", value=42):
    document = ItemDocument(raw)
    spec = next(item["spec"] for item in document.schemas[table]["fields"] if item["spec"].key == field)
    _, start, row = document._row(table, row_id)
    document.plain[start:start + len(row)] = write_field(row, spec, value, "<")
    return document.export()


def opaque(raw, index, value):
    document = ItemDocument(raw)
    document.plain[document.members["Untouched.bin"].offset + index] = value
    return document.export()


@pytest.fixture
def base():
    return make_archive()


def test_noop_is_byte_exact(base):
    assert compose(base, [])[0] == base
    result, report = compose(base, [("unchanged", base)])
    assert result == base and report["changedCells"] == 0
    assert report["baseSha256"] == report["outputSha256"] == sha256(base).hexdigest()


def test_same_row_independent_fields_compose(base):
    a = changed(base, field="sellValue", value=42)
    b = changed(base, field="goodsType", value=1)
    result, report = compose(base, [("a", a), ("b", b)])
    document = ItemDocument(result)
    assert document.value("EquipParamGoods", 100, "sellValue") == 42
    assert document.value("EquipParamGoods", 100, "goodsType") == 1
    assert report["changedCells"] == 2 and report["conflicts"] == []
    original, merged = inflate(base), inflate(result)
    changed_offsets = {i for i, (x, y) in enumerate(zip(original, merged)) if x != y}
    allowed = {i for mod in (a, b) for i, (x, y) in enumerate(zip(original, inflate(mod))) if x != y}
    assert changed_offsets == allowed


def test_independent_rows_and_late_vanilla_do_not_erase_edits(base):
    a, b = changed(base, row_id=100, value=42), changed(base, row_id=101, value=84)
    result, _ = compose(base, [("a", a), ("b", b), ("unchanged", base)])
    document = ItemDocument(result)
    assert document.value("EquipParamGoods", 100, "sellValue") == 42
    assert document.value("EquipParamGoods", 101, "sellValue") == 84


def test_identical_changes_coalesce(base):
    a = changed(base, value=42)
    result, report = compose(base, [("a", a), ("b", a)])
    assert result == a and report["changedCells"] == 1
    assert report["conflicts"] == []


def test_numeric_cell_conflicts_even_when_modified_bytes_are_disjoint(base):
    a, b = changed(base, value=1), changed(base, value=256)
    with pytest.raises(ConflictError) as failure:
        compose(base, [("a", a), ("b", b)])
    conflict = failure.value.report["conflicts"][0]
    assert conflict["field"] == "sellValue" and conflict["rowId"] == 100
    assert conflict["winner"] == "b" and conflict["loser"] == "a"
    result, report = compose(base, [("a", a), ("b", b)], policy="last-wins")
    assert ItemDocument(result).value("EquipParamGoods", 100, "sellValue") == 256
    assert len(report["conflicts"]) == 1
    reversed_result, _ = compose(base, [("b", b), ("a", a)], policy="last-wins")
    assert ItemDocument(reversed_result).value("EquipParamGoods", 100, "sellValue") == 1


def test_neighboring_flags_in_one_byte_compose(base):
    document = ItemDocument(base)
    fields = [item["spec"] for item in document.schemas["EquipParamGoods"]["fields"]
              if not item["spec"].padding and item["spec"].bit_size == 1]
    first, second = next((a, b) for a in fields for b in fields
                         if a.offset == b.offset and a.bit_offset != b.bit_offset)
    a = changed(base, field=first.key, value=1)
    b = changed(base, field=second.key, value=1)
    result, report = compose(base, [("a", a), ("b", b)])
    merged = ItemDocument(result)
    assert merged.value("EquipParamGoods", 100, first.key) == 1
    assert merged.value("EquipParamGoods", 100, second.key) == 1
    assert not report["conflicts"]


def test_unknown_member_is_atomic_not_a_byte_merge(base):
    a, b = opaque(base, 0, 65), opaque(base, 1, 66)
    with pytest.raises(ConflictError) as failure:
        compose(base, [("a", a), ("b", b)])
    assert failure.value.report["conflicts"][0]["granularity"] == "member"
    result, _ = compose(base, [("a", a), ("b", b)], policy="last-wins")
    assert result == b


def test_opaque_member_and_known_field_coexist(base):
    a, b = opaque(base, 0, 65), changed(base, value=42)
    result, report = compose(base, [("a", a), ("b", b)])
    document = ItemDocument(result)
    assert document.plain[document.members["Untouched.bin"].offset] == 65
    assert document.value("EquipParamGoods", 100, "sellValue") == 42
    assert not report["conflicts"]


@pytest.mark.parametrize("kind", ["binder-header", "padding", "row-id"])
def test_structural_or_protected_changes_are_not_silently_dropped(base, kind):
    document = ItemDocument(base)
    if kind == "binder-header":
        document.plain[4] ^= 1
    elif kind == "row-id":
        member = document.members["EquipParamGoods.param"]
        struct.pack_into("<i", document.plain, member.offset + 48, 999)
    else:
        spec = next(item["spec"] for item in document.schemas["EquipParamGoods"]["fields"]
                    if item["spec"].padding)
        start = document._row("EquipParamGoods", 100)[1] + spec.offset
        document.plain[start] ^= 1 << (spec.bit_offset or 0)
    with pytest.raises(CompositionError):
        compose(base, [("unsupported", document.export())])


def test_duplicate_ids_and_invalid_policy_fail(base):
    with pytest.raises(CompositionError, match="Duplicate"):
        compose(base, [("a", base), ("a", base)])
    with pytest.raises(CompositionError, match="policy"):
        compose(base, [], policy="automatic-magic")


def test_cell_preserves_neighbor_bits():
    cell = Cell("test", "table", 1, "flag", 0, 1, 0b00000110)
    data = bytearray([0b10101001])
    cell.write(data, b"\x06")
    assert data == bytearray([0b10101111])
    assert cell.read(data) == b"\x06"
