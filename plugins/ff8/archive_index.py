"""List what is inside the installed game's archives.

The plugin reads the files it edits and writes only to the project copy, so a
modder had no way to see what an archive holds or where a file lives: the
editability audit lists "archive browse, extract and repack" as Deling's area
and as a gap here.

This reads the same FS/FI/FL triplets `fs_archive` already parses, and nothing
else: it lists entries and their stored sizes, it does not read entry contents
and it never writes to the installation. Extraction and repacking are separate
jobs and are not claimed here.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil

from . import paths
from .fs_archive import FsArchive


# The triplets the plugin's own extractor knows, plus the two large ones a
# modder looks into most often. A prefix that is absent is reported as absent
# rather than hidden.
ARCHIVE_PREFIXES = {
    "main": "main",
    "menu": "menu",
    "battle": "battle",
    "field": "field",
    "world": "world",
    "magic": "magic",
}
DEFAULT_PAGE_SIZE = 60
MAX_PAGE_SIZE = 500


def _prefix(name: str) -> Path:
    key = str(name or "").strip().lower()
    if key not in ARCHIVE_PREFIXES:
        raise ValueError(f"Unknown archive: {name}")
    return paths.GAME_ROOT / "Data" / "lang-en" / ARCHIVE_PREFIXES[key]


def archives() -> dict:
    """One row per archive: how many entries it holds, and whether it is here."""
    rows = []
    for name in ARCHIVE_PREFIXES:
        prefix = _prefix(name)
        row = {"name": name, "prefix": str(prefix), "available": False,
               "entries": 0, "bytes": 0, "message": ""}
        if not prefix.with_suffix(".fi").is_file() or not prefix.with_suffix(".fl").is_file():
            row["message"] = "This archive is not installed."
            rows.append(row)
            continue
        try:
            archive = FsArchive(prefix)
        except (ValueError, OSError) as error:
            row["message"] = f"This archive could not be read: {error}"
            rows.append(row)
            continue
        row.update(available=True, entries=len(archive.entries),
                   bytes=sum(entry.unpacked_length for entry in archive.entries))
        rows.append(row)
    return {"rows": rows, "source": str(paths.GAME_ROOT)}


def entries(name: str, query: str = "", page: int = 0,
            page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    """A page of one archive's entries, filtered by a case-insensitive search."""
    prefix = _prefix(name)
    if not prefix.with_suffix(".fi").is_file():
        raise ValueError(f"The {name} archive is not installed")
    archive = FsArchive(prefix)
    pattern = str(query or "").strip()
    matcher = re.compile(re.escape(pattern), re.IGNORECASE) if pattern else None
    rows = [{"index": entry.index, "name": entry.name, "basename": entry.basename,
             "bytes": entry.unpacked_length, "compressed": entry.compressed,
             "offset": entry.offset}
            for entry in archive.entries
            if matcher is None or matcher.search(entry.name)]
    size = max(1, min(MAX_PAGE_SIZE, int(page_size) or DEFAULT_PAGE_SIZE))
    pages = max(1, (len(rows) + size - 1) // size)
    current = max(0, min(pages - 1, int(page) or 0))
    start = current * size
    return {"archive": str(name).strip().lower(), "prefix": str(prefix),
            "query": pattern, "matched": len(rows), "page": current, "pageSize": size,
            "pages": pages, "total": len(archive.entries),
            "rows": rows[start:start + size]}


def extract(name: str, index: int, project_root: Path | None = None) -> dict:
    """Write one entry's bytes into the project's own extracted folder.

    Browsing reads metadata; this is the one place entry contents are read, and
    they are written into the project, never back into the installation. The
    copy is bounded like every other project write: one previous copy is kept.
    """
    prefix = _prefix(name)
    if not prefix.with_suffix(".fi").is_file():
        raise ValueError(f"The {name} archive is not installed")
    archive = FsArchive(prefix)
    wanted = int(index)
    entry = next((item for item in archive.entries if item.index == wanted), None)
    if entry is None:
        raise ValueError(f"The {name} archive has no entry {wanted}")
    root = Path(project_root) if project_root is not None else paths.PROJECT_ROOT
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", entry.basename) or f"entry-{wanted}"
    destination = root / EXTRACTED_ROOT / str(name).strip().lower() / safe
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        shutil.copy2(destination, destination.with_name(f"{destination.name}.bak"))
    data = archive.extract(entry)
    destination.write_bytes(data)
    return {"archive": str(name).strip().lower(), "index": wanted, "name": entry.name,
            "bytes": len(data), "path": str(destination), "project": str(root)}
EXTRACTED_ROOT = "extracted"
