"""Verify the battle model animation-sequence section (section 5)."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import assets, paths  # noqa: E402


def main() -> int:
    root = paths.BASELINE_ROOT / "battle"
    files = sorted(root.glob("c0m*.dat"))
    assert files, "the baseline holds no battle model files"

    parsed = []
    refused = []
    sequences = 0
    empty_ids = 0
    for path in files:
        try:
            payload = assets.animation_sequences(path.name, path.read_bytes())
        except ValueError as error:
            refused.append((path.name, str(error)))
            continue
        if payload is None:
            refused.append((path.name, "not a model file with that section"))
            continue
        parsed.append(payload)
        sequences += payload["present"]
        empty_ids += payload["count"] - payload["present"]
        # The table is a count, then one offset per id, and every id is listed.
        assert [row["id"] for row in payload["rows"]] == list(range(1, payload["count"] + 1))
        assert payload["tableBytes"] == 2 + 2 * payload["count"]
        present = sorted(row["offset"] - payload["sectionOffset"]
                         for row in payload["rows"] if row["present"])
        assert len(present) == payload["present"]
        starts = [row["offset"] for row in payload["rows"] if row["present"]]
        assert len(set(starts)) == len(starts), payload["file"]
        # The spans tile the section: in file order, each starts where the
        # previous one ends.
        ordered = sorted((row["offset"] - payload["sectionOffset"], row["bytes"])
                         for row in payload["rows"] if row["present"])
        for (start, size), (following, _) in zip(ordered, ordered[1:]):
            assert start + size == following, payload["file"]
        # The byte code starts right after the table and runs to the section
        # end, with nothing between the spans.
        assert ordered[0][0] == payload["tableBytes"], payload["file"]
        assert ordered[-1][0] + ordered[-1][1] == payload["sectionBytes"], payload["file"]

    # c0m127.dat is the documented two-section exception and has no such section.
    assert len(parsed) == len(files) - 1, (len(parsed), len(files))
    assert [name for name, _ in refused] == ["c0m127.dat"], refused
    assert sequences > 2000, sequences

    sample = next(payload for payload in parsed if payload["file"] == "c0m001.dat")
    assert sample["count"] == 14 and sample["present"] == 11, sample["count"]
    assert sample["rows"][0]["bytes"] > 0 and sample["rows"][0]["sha256"]
    assert any(not row["present"] for row in sample["rows"]), "no empty id in c0m001"

    # A file that is not a model container is refused rather than guessed at.
    assert assets.animation_sequences("c0m127.dat",
                                      (root / "c0m127.dat").read_bytes()) is None
    assert assets.animation_sequences("kernel.bin", b"not a model") is None
    print(json.dumps({"files": len(files), "parsed": len(parsed), "sequences": sequences,
                      "emptyIds": empty_ids, "refused": [name for name, _ in refused],
                      "c0m001": [sample["count"], sample["present"]]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
