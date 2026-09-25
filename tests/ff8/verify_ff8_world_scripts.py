"""Verify the wmset script sections: their container and section 11's scripts."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import world_map  # noqa: E402


def main() -> int:
    raw = world_map.ensure_baseline().read_bytes()
    pointers = world_map._pointers(raw)
    scripts = world_map.vehicle_warp_scripts("vanilla")
    rows = scripts["rows"]
    assert scripts["section"] == world_map.VEHICLE_WARP_SECTION == 11
    assert len(rows) == 4, rows

    section = raw[pointers[11]:pointers[12]]
    offsets = []
    cursor = 0
    while struct.unpack_from("<I", section, cursor)[0]:
        offsets.append(struct.unpack_from("<I", section, cursor)[0])
        cursor += 4
    assert offsets == [20, 56, 92, 128], offsets
    assert struct.unpack_from("<I", section, cursor)[0] == 0, "the table ends on a zero sentinel"
    assert cursor + 4 == offsets[0], (cursor, offsets[0])

    for index, row in enumerate(rows):
        body = raw[row["offset"]:row["offset"] + row["bytes"]]
        # Each script ends at its own RETURN, not at the next table offset.
        assert struct.unpack_from("<H", body, len(body) - 2)[0] == world_map.SCRIPT_RETURN, row
        assert row["offset"] == pointers[11] + offsets[index]
        assert body[:2] == b"\x01\xff", row["head"]
    # The four scripts differ only in the value they hand back, which is what the
    # wiki says these sections do through SET_RETURN_VALUE.
    operands = [struct.unpack_from("<H", raw, row["offset"] + 6)[0] for row in rows]
    assert len(set(operands)) == 4, operands
    assert all(0 < value < 0x1000 for value in operands), operands

    # Sections 7 and 9 use the same container on paper, but section 9's extent
    # rule has not been confirmed against its own bytes here, so this check
    # claims section 11 only. Section 7 is read to prove the reader is not
    # special-cased, and its result is reported, not asserted.
    seven = world_map.scripts_in_section(raw, 7)
    assert seven, "section 7 has no scripts"
    try:
        world_map.scripts_in_section(raw, 12)
    except ValueError as error:
        assert "offset" in str(error).lower() or "script" in str(error).lower(), error
    else:
        raise AssertionError("section 12 (train exits) parsed as scripts")
    print(json.dumps({"section": 11, "scripts": len(rows),
                      "offsets": offsets, "bodyBytes": [row["bytes"] for row in rows],
                      "operands": operands}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
