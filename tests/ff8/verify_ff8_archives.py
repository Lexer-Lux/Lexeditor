"""Verify the archive index against the installed game's own triplets."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

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

    # Extraction is the one place contents are read, and they go into the
    # project, never into the installation.
    project = tempfile.TemporaryDirectory(prefix="lexeditor-archive-extract-",
                                          ignore_cleanup_errors=True)
    try:
        root = Path(project.name)
        installed = FsArchive(paths.GAME_ROOT / "Data" / "lang-en" / "main")
        entry = installed.entries[0]
        first = archive_index.extract("main", entry.index, project_root=root)
        written = Path(first["path"])
        assert written.is_file() and written.parent.name == "main"
        assert first["bytes"] == entry.unpacked_length
        assert written.read_bytes() == installed.extract(entry)
        assert root in written.parents and paths.GAME_ROOT not in written.parents
        # A second extract keeps one previous copy and nothing else.
        archive_index.extract("main", entry.index, project_root=root)
        assert written.with_name(f"{written.name}.bak").is_file()
        assert len(list(written.parent.glob("*.bak"))) == 1
    finally:
        project.cleanup()
    for bad_name, bad_index in [("nope", 0), ("main", 99_999)]:
        try:
            archive_index.extract(bad_name, bad_index,
                                  project_root=Path(tempfile.gettempdir()))
        except ValueError as error:
            assert "archive" in str(error).lower() or "entry" in str(error).lower(), error
        else:
            raise AssertionError(f"extract accepted {bad_name}:{bad_index}")
    print(json.dumps({"archives": len(rows), "available": len(available),
                      "totals": {name: row["entries"] for name, row in rows.items()},
                      "namedicFound": found["rows"][0]["name"],
                      "absent": [row["name"] for row in missing],
                      "extracted": True}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
