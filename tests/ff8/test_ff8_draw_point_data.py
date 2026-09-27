"""The draw point Hext patch: one byte per changed draw ID, read back exactly."""
import pytest

from plugins.ff8 import draw_point_data as data


def test_encode_packs_magic_refill_and_high_yield():
    assert data.encode({"magicId": 21, "refill": True, "highYield": False}) == 0x55
    assert data.encode({"magicId": 21, "refill": False, "highYield": True}) == 0x95


@pytest.mark.parametrize("edit", [
    {"magicId": 64, "refill": True, "highYield": False},
    {"magicId": -1, "refill": True, "highYield": False},
    {"magicId": True, "refill": True, "highYield": False},
    {"magicId": 3, "refill": 1, "highYield": False},
])
def test_encode_refuses_values_the_byte_cannot_hold(edit):
    with pytest.raises(ValueError):
        data.encode(edit)


def test_patch_writes_only_changed_bytes_and_reads_them_back():
    vanilla = bytes(range(256))
    text = data.build_patch({129: 0x95, 1: 0}, vanilla)
    # Draw ID 1 already holds 0 in this table, so only 129 is written.
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    assert lines == [f"{data.TABLE_ADDRESS + 128:X} = 95  # draw ID 129"]
    assert data.parse_patch(text) == {129: 0x95}


def test_parse_ignores_lines_outside_the_table():
    text = f"{data.TABLE_ADDRESS - 1:X} = 11\n{data.TABLE_ADDRESS + 256:X} = 22\n{data.TABLE_ADDRESS:X} = 33\n"
    assert data.parse_patch(text) == {1: 0x33}
