"""Verify the archive index against the installed game's own triplets."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plugins.ff8 import archive_index, paths  # noqa: E402
from plugins.ff8.fs_archive import FsArchive  # noqa: E402


def main() -> int:
    listing = archive_index.archives()
    rows = {row["name"]: row for row in listing["rows"]}
    assert set(rows) == set(archive_index.ARCHIVE_PREFIXES), rows.keys()
    available = [row for row in rows.values() if row["available"]]
    assert available, "no archive of the installed game could be listed"
    # The counts come from the same parser the plugin's own extraction uses, so
    # they must agree with it exactly.
    for row in available:
        archive = FsArchive(paths.GAME_ROOT / "Data" / "lang-en" / row["name"])
        assert row["entries"] == len(archive.entries), row["name"]
        assert row["bytes"] == sum(entry.unpacked_length for entry in archive.entries)
        assert rows[row["name"]]["message"] == ""
    missing = [row for row in rows.values() if not row["available"]]
    for row in missing:
        assert row["message"], row

    # A search finds a known entry, and paging stays inside its own bounds.
    main_page = archive_index.entries("main", page_size=10)
    assert main_page["total"] == rows["main"]["entries"]
    assert len(main_page["rows"]) == 10 and main_page["pages"] >= 1
    found = archive_index.entries("main", query="namedic")
    assert found["matched"] == 1 and found["rows"][0]["basename"] == "namedic.bin", found
    assert archive_index.entries("main", query="NAMEDIC")["matched"] == 1
    assert archive_index.entries("main", query="not-there-at-all")["matched"] == 0
    # A page past the end clamps instead of returning nothing.
    last = archive_index.entries("main", page=99, page_size=5)
    assert last["page"] == last["pages"] - 1, last
    assert archive_index.entries("main", page=-3)["page"] == 0

    for bad, expected in [("nope", "unknown archive"), ("", "unknown archive")]:
        try:
            archive_index.entries(bad)
        except ValueError as error:
            assert expected in str(error).lower(), error
        else:
            raise AssertionError(f"the archive index accepted {bad!r}")
    # The index never reads entry contents: every row carries only metadata.
    assert set(main_page["rows"][0]) == {"index", "name", "basename", "bytes",
                                         "compressed", "offset"}
    print(json.dumps({"archives": len(rows), "available": len(available),
                      "totals": {name: row["entries"] for name, row in rows.items()},
                      "namedicFound": found["rows"][0]["name"],
                      "absent": [row["name"] for row in missing]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
