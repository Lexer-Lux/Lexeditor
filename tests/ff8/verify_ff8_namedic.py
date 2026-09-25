"""Verify the namedic.bin name list and the writer that rebuilds it."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import kernel_text, namedic, paths  # noqa: E402


def payloads(raw: bytes) -> list[bytes]:
    document = namedic.parse(raw)
    return [raw[entry["offset"]:entry["offset"] + entry["length"]]
            for entry in document["entries"]]


def rejected(raw: bytes, edits: list[dict], expected: str) -> None:
    try:
        namedic.apply_edits(raw, edits)
    except ValueError as error:
        assert expected.lower() in str(error).lower(), error
    else:
        raise AssertionError(f"namedic.bin writer accepted invalid {expected}")


def main() -> int:
    raw = namedic.ensure_baseline().read_bytes()
    document = namedic.parse(raw)
    assert document["count"] == len(document["entries"]) == 32
    names = [entry["text"] for entry in document["entries"]]
    # The shipped list is the game's own place names and inserted words.
    assert names[0] == "Galbadia" and names[2] == "Balamb", names[:3]
    assert names[30] == "Garden" and names[21] == "learns", names[-3:]
    assert document["entries"][0]["offset"] == namedic.COUNT_SIZE + 32 * namedic.OFFSET_SIZE
    # An untouched list is written back byte for byte.
    assert namedic.apply_edits(raw, []) == raw

    # A longer name moves the names after it and nothing else.
    longer = namedic.apply_edits(raw, [{"index": 0, "text": "Galbadia Region"}])
    rewritten = namedic.parse(longer)
    assert rewritten["count"] == 32
    assert [entry["text"] for entry in rewritten["entries"]] == [
        "Galbadia Region", *names[1:]]
    before, after = payloads(raw), payloads(longer)
    assert all(left == right for left, right in zip(before[1:], after[1:])), \
        "a name the caller did not edit changed"
    assert after[0] == kernel_text.encode("Galbadia Region", compress=False) + b"\x00"
    assert len(longer) == len(raw) + len(" Region")

    # A shorter name pulls them back.
    shorter = namedic.apply_edits(raw, [{"index": 1, "text": "Est"}])
    assert [entry["text"] for entry in namedic.parse(shorter)["entries"]][:3] == [
        "Galbadia", "Est", "Balamb"]
    assert len(shorter) == len(raw) - 3
    # Two names can move at once, and the table is rebuilt once.
    both = namedic.parse(namedic.apply_edits(raw, [
        {"index": 7, "text": "Fishermans Horizon Station"},
        {"index": 8, "text": "East"},
    ]))
    assert both["entries"][7]["text"] == "Fishermans Horizon Station"
    assert both["entries"][8]["text"] == "East"
    assert both["entries"][9]["text"] == names[9]
    assert [entry["offset"] for entry in both["entries"]] == sorted(
        entry["offset"] for entry in both["entries"])

    rejected(raw, [{"index": 0, "text": "Ok"}, {"index": 0, "text": "Also"}], "two edits")
    rejected(raw, [{"index": 32, "text": "Past the end"}], "no name 32")
    rejected(raw, [{"index": -1, "text": "Before the start"}], "no name -1")
    rejected(raw, [{"index": 0}], "needs text")
    rejected(raw, [{"index": 0, "text": "a\x00b"}], "null byte")
    rejected(raw, [{"index": 0, "text": "snowman \u2603"}], "not available")
    rejected(raw, [{"text": "no index"}], "needs an index")

    project = tempfile.TemporaryDirectory(prefix="lexeditor-namedic-", ignore_cleanup_errors=True)
    previous_project = paths.PROJECT_ROOT
    try:
        paths.PROJECT_ROOT = Path(project.name)
        paths.DIRECT_ROOT = paths.PROJECT_ROOT / "direct"
        saved = namedic.save([{"index": 0, "text": "Lexeditor Test"}])
        assert saved["source"] == "current"
        assert saved["entries"][0]["text"] == "Lexeditor Test"
        written = paths.DIRECT_ROOT / namedic.DIRECT_RELATIVE
        assert written.is_file()
        assert namedic.parse(written.read_bytes())["entries"][1]["text"] == "Esthar"
        assert namedic.source_path("current") == written
        assert namedic.source_path("vanilla") == namedic.ensure_baseline()
        again = namedic.save([{"index": 0, "text": "Lexeditor Test Two"}])
        assert again["entries"][0]["text"] == "Lexeditor Test Two"
        assert written.with_name("namedic.bin.bak").is_file(), \
            "a save keeps one rolling backup"
    finally:
        paths.PROJECT_ROOT = previous_project
        paths.DIRECT_ROOT = previous_project / "direct"
        project.cleanup()

    # The extracted baseline is read-only source: the writer never touched it.
    assert namedic.parse(namedic.ensure_baseline().read_bytes())["count"] == 32
    print(json.dumps({
        "entries": document["count"],
        "first": names[0],
        "last": names[-1],
        "untouchedBytes": f"{len(before[1:])} names",
        "lengthChange": [len(shorter) - len(raw), len(longer) - len(raw)],
        "rejections": 7,
        "saveReadBack": True,
    }, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
