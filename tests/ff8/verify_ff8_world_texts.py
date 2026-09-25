"""Verify the world map's own dialog strings (wmset section 13)."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import paths, world_map  # noqa: E402


def main() -> int:
    payload = world_map.side_quest_texts("vanilla")
    rows = payload["rows"]
    assert payload["section"] == world_map.SIDE_QUEST_TEXT_SECTION == 13
    assert len(rows) == 151, len(rows)

    raw = world_map.ensure_baseline().read_bytes()
    pointers = world_map._pointers(raw)
    section = raw[pointers[13]:pointers[14]]
    offsets = []
    cursor = 0
    while struct.unpack_from("<I", section, cursor)[0]:
        offsets.append(struct.unpack_from("<I", section, cursor)[0])
        cursor += 4
    assert len(offsets) == len(rows), (len(offsets), len(rows))
    assert offsets == sorted(offsets), "the offsets are read in file order"
    assert cursor + 4 == offsets[0], (cursor, offsets[0])
    assert [row["offset"] - pointers[13] for row in rows] == offsets
    # Each string runs to its terminator inside its own span; whatever follows
    # that terminator is zero padding, not text.
    spans = [stop - start for start, stop in zip(offsets, offsets[1:] + [len(section)])]
    bad = [(row["index"], row["bytes"], span) for row, span in zip(rows, spans)
           if not 0 <= row["bytes"] <= span]
    assert not bad, bad[:4]
    for row, start, stop in zip(rows, offsets, offsets[1:] + [len(section)]):
        tail = section[start + row["bytes"]:stop]
        assert tail[:1] == b"\x00" and not tail.strip(b"\x00"), (row["index"], tail)

    # Every string decodes to something, and the codec turns each byte into a
    # glyph or a reversible {xHH} token, so nothing is silently dropped.
    # An entry may be a null string (a span holding only its terminator); every
    # other one decodes to text.
    empty = [row["index"] for row in rows if row["bytes"] == 0]
    assert len(empty) <= 5, empty
    assert all(row["text"] for row in rows if row["bytes"]), "a non-empty entry decoded to nothing"
    joined = "\n".join(row["text"] for row in rows)
    assert "Get off?" in joined and "Gil to ride" in joined, joined[:200]
    assert sum(1 for row in rows if "Station" in row["text"]) >= 3

    # Six strings use a control byte the reference does not name. It stays a
    # token plus its argument rather than being given an invented meaning.
    unknown = [row for row in rows if "{x0D}" in row["text"]]
    assert len(unknown) == 6, len(unknown)

    # An offset that points outside the section is refused rather than read.
    patched = bytearray(raw)
    patched[pointers[13] + 4:pointers[13] + 8] = (len(section) + 8).to_bytes(4, "little")
    project = tempfile.TemporaryDirectory(prefix="lexeditor-world-texts-",
                                          ignore_cleanup_errors=True)
    previous = paths.BASELINE_ROOT
    try:
        root = Path(project.name) / "baseline" / "en"
        (root / "world").mkdir(parents=True)
        target = root / "world" / "wmsetus.obj"
        target.write_bytes(bytes(patched))
        # The cache only accepts a copy whose source fingerprint matches the
        # installed archive, so the patched file must carry that fingerprint or
        # it would be replaced by a fresh extraction before it is read.
        target.with_suffix(".obj.source.json").write_text(
            json.dumps(world_map._fingerprint(world_map._archive_prefix())), encoding="utf-8")
        paths.BASELINE_ROOT = root
        try:
            world_map.side_quest_texts("vanilla")
        except ValueError as error:
            assert "outside" in str(error), error
        else:
            raise AssertionError("an offset outside the section was accepted")
    finally:
        paths.BASELINE_ROOT = previous
        project.cleanup()

    # The last offset reaches the end of the section, so no string is truncated
    # by a header or a footer.
    assert offsets[-1] < len(section)
    print(json.dumps({"section": 13, "strings": len(rows),
                      "nullStrings": empty,
                      "undecodedControlByte": len(unknown),
                      "example": rows[4]["text"][:60]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
