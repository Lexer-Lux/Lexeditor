"""Static and binary round-trip contract for FF8 kernel text editing.

Primary format evidence:
- FF8UltimateEditor 343d97e9e15023b15b2956b30c1c80cd93969164:
  ShumiTranslator/model/kernel/kernelmanager.py and kernelsectiondata.py.
- OpenVIII b600dda73486c522e6b33bd1e0f2f7f1063e35b4:
  Encoding/Sources/FF8TextEncoder.cs and FF8TextEncodingCodepage.cs.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games.ff8 import formats, kernel_text  # noqa: E402


def pack_sections(payloads: list[bytes]) -> bytes:
    header_size = 4 * (len(payloads) + 1)
    starts, cursor = [], header_size
    for payload in payloads:
        starts.append(cursor)
        cursor += len(payload)
    return len(payloads).to_bytes(4, "little") + b"".join(
        start.to_bytes(4, "little") for start in starts) + b"".join(payloads)


def synthetic_kernel() -> bytes:
    payloads: list[bytes] = []
    for section_id in range(1, 32):
        definition = formats.SECTIONS[section_id]
        size = int(definition["number_sub_section"]) * int(definition["sub_section_size"])
        payload = bytearray(size)
        offset_count = int(definition["sub_section_nb_text_offset"])
        record_size = int(definition["sub_section_size"])
        for record_id in range(int(definition["number_sub_section"])):
            for slot in range(offset_count):
                position = record_id * record_size + slot * 2
                payload[position:position + 2] = b"\xff\xff"
        if offset_count:
            payload[0:2] = b"\0\0"
        payloads.append(bytes(payload))
    payloads.extend([b"A\0\0\0" for _ in range(32, 57)])
    return pack_sections(payloads)


def erase_text_offsets(payload: bytes, definition: dict) -> bytes:
    result = bytearray(payload)
    count = int(definition["number_sub_section"])
    size = int(definition["sub_section_size"])
    text_offsets = int(definition["sub_section_nb_text_offset"])
    for record_id in range(count):
        for slot in range(text_offsets):
            position = record_id * size + slot * 2
            result[position:position + 2] = b"\0\0"
    return bytes(result)


def text_bytes_by_identity(data_section: bytes, text_section: bytes, definition: dict) -> dict:
    slots = kernel_text._slots(data_section, definition)
    strings = kernel_text._strings(text_section, slots)
    return {(slot.record_id, slot.slot): strings[slot.text_offset]
            for slot in slots if slot.text_offset != kernel_text.UNUSED_OFFSET}


def exercise(data: bytes) -> None:
    parsed = kernel_text.rows(data, formats.SECTIONS)
    assert len(parsed["sections"]) == 25
    rebuilt, changed = kernel_text.apply_edits(data, formats.SECTIONS, [])
    assert changed == 0 and rebuilt == data, "a no-op save must be byte-identical"

    target = next(row for row in parsed["rows"] if row["sectionId"] == 33)
    replacement = "Longer {Squall} text\n100%"
    edited, changed = kernel_text.apply_edits(data, formats.SECTIONS, [{
        "sectionId": target["sectionId"], "recordId": target["recordId"],
        "slot": target["slot"], "value": replacement,
    }])
    assert changed == 1
    reread = kernel_text.rows(edited, formats.SECTIONS)
    match = next(row for row in reread["rows"] if
                 (row["sectionId"], row["recordId"], row["slot"]) ==
                 (target["sectionId"], target["recordId"], target["slot"]))
    assert match["value"] == replacement

    before, _ = kernel_text._split_sections(data, len(formats.SECTIONS))
    after, starts = kernel_text._split_sections(edited, len(formats.SECTIONS))
    assert starts == sorted(starts) and starts[-1] <= len(edited)
    for section_id in range(1, 57):
        if section_id not in (2, 33):
            assert after[section_id - 1] == before[section_id - 1], section_id
    assert erase_text_offsets(after[1], formats.SECTIONS[2]) == erase_text_offsets(
        before[1], formats.SECTIONS[2]), "non-offset bytes in the linked data section changed"
    original_strings = text_bytes_by_identity(before[1], before[32], formats.SECTIONS[2])
    rebuilt_strings = text_bytes_by_identity(after[1], after[32], formats.SECTIONS[2])
    target_key = (target["recordId"], target["slot"])
    assert all(rebuilt_strings[key] == value for key, value in original_strings.items()
               if key != target_key), "an unedited encoded string changed"


def main() -> int:
    assert kernel_text.decode(kernel_text.encode('A"Z ■↓™')) == 'A"Z ■↓™'
    assert kernel_text.decode(kernel_text.encode("{Squall}{L2}{CardReceived}")) == \
        "{Squall}{L2}{CardReceived}"
    for bad in ("snowman ☃", "{unknown}", "{x00}"):
        try:
            kernel_text.encode(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe text was accepted: {bad}")

    fixture = synthetic_kernel()
    exercise(fixture)
    payloads, _ = kernel_text._split_sections(fixture, len(formats.SECTIONS))
    expanded_record = bytearray(int(formats.SECTIONS[2]["sub_section_size"]))
    expanded_record[0:2] = (2).to_bytes(2, "little")
    expanded_record[2:4] = (4).to_bytes(2, "little")
    payloads[1] += bytes(expanded_record)
    payloads[32] = b"A\0B\0C\0\0\0"
    expanded = pack_sections(payloads)
    expanded_rows = kernel_text.rows(expanded, formats.SECTIONS)["rows"]
    assert any(row["sectionId"] == 33 and row["recordId"] == 57
               for row in expanded_rows), "growable magic text was not read"
    expanded_edit, changed = kernel_text.apply_edits(expanded, formats.SECTIONS, [{
        "sectionId": 33, "recordId": 57, "slot": 1, "value": "Expanded magic",
    }])
    assert changed == 1 and any(row["value"] == "Expanded magic" for row in
                                kernel_text.rows(expanded_edit, formats.SECTIONS)["rows"])

    payloads, _ = kernel_text._split_sections(fixture, len(formats.SECTIONS))
    payloads[32] = payloads[32][:-1] + b"\x01"
    corrupt = pack_sections(payloads)
    try:
        kernel_text.rows(corrupt, formats.SECTIONS)
    except ValueError as error:
        assert "trailing" in str(error)
    else:
        raise AssertionError("unreferenced text bytes were accepted")

    baseline = Path.home() / "AppData/Local/Lexeditor/game-data/ff8/baseline/en/main/kernel.bin"
    if baseline.is_file():
        data = baseline.read_bytes()
        assert int.from_bytes(data[:4], "little") == 56
        assert len(kernel_text.rows(data, formats.SECTIONS)["rows"]) == 1322
        exercise(data)

    source = (ROOT / "games/ff8/editor.html").read_text(encoding="utf-8")
    server = (ROOT / "games/ff8/server.py").read_text(encoding="utf-8")
    assert '"text"' in source and 'renderText' in source
    assert '"/api/text"' in server and '"/api/text/save"' in server
    print("FF8 kernel text issue 57 verifier: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
