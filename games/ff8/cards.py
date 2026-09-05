"""Existing Triple Triad records for the supported Steam English executable.

Schema: FF8UltimateEditor CCGroup/card.py and cardwidget.py, exe.json.
No allocation or removal of card IDs is implied by this fixed-table editor.
"""
from __future__ import annotations

import struct
import json
import threading
import os
import tempfile
from pathlib import Path

from . import executable_text

COUNT = 110
RECORD_SIZE = 8
TABLE_OFFSETS = (0x796508, 0x874D00)
FIELDS = ("top", "bottom", "left", "right", "element", "power")
ELEMENTS = {0: "None", 1: "Fire", 2: "Ice", 4: "Thunder", 8: "Earth",
            16: "Poison", 32: "Wind", 64: "Water", 128: "Holy"}
MANIFEST = "lexeditor-cards.json"
# The supported Steam English executable is detected by FFNx as en_nv.
# See gameplay_settings.FFNX_HEXT_SUFFIX; Direct Mode text still uses ff8/en.
HEXT = Path("hext") / "ff8" / "en_nv" / "lexeditor-cards.txt"
_LOCK = threading.RLock()


def _integer(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number")
    return value


def _virtual_address(exe: bytes, offset: int, length: int) -> int:
    """Resolve a complete file-backed range through the PE section table."""
    pe = struct.unpack_from("<I", exe, 0x3C)[0]
    if exe[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Invalid PE signature")
    count = struct.unpack_from("<H", exe, pe + 6)[0]
    optional_size = struct.unpack_from("<H", exe, pe + 20)[0]
    if struct.unpack_from("<H", exe, pe + 24)[0] != 0x10B:
        raise ValueError("Cards require a PE32 executable")
    image_base = struct.unpack_from("<I", exe, pe + 24 + 28)[0]
    for i in range(count):
        section = pe + 24 + optional_size + i * 40
        _, rva, raw_size, raw_start = struct.unpack_from("<4I", exe, section + 8)
        if raw_start <= offset and offset + length <= raw_start + raw_size:
            return image_base + rva + offset - raw_start
    raise ValueError("Card table is outside a file-backed PE section")


def read_tables(exe: bytes) -> tuple[bytes, bytes]:
    executable_text._validate_executable(exe)
    tables = tuple(exe[o:o + COUNT * RECORD_SIZE] for o in TABLE_OFFSETS)
    for offset, table in zip(TABLE_OFFSETS, tables):
        _virtual_address(exe, offset, COUNT * RECORD_SIZE)
        if len(table) != COUNT * RECORD_SIZE:
            raise ValueError("Incomplete card table")
    if tables[0] != tables[1]:
        raise ValueError("Menu and game card tables disagree")
    return tables


def read_cards(exe: bytes, names: list[str]) -> list[dict]:
    table = read_tables(exe)[0]
    if len(names) != COUNT:
        raise ValueError("Cards require exactly 110 names")
    return [dict(id=i, name=names[i], **dict(zip(FIELDS, table[i * 8:i * 8 + 6])))
            for i in range(COUNT)]


def apply_edits(table: bytes, edits: list[dict]) -> tuple[bytes, int]:
    """Apply validated scalar edits; retain both unknown bytes and other cards.

    Edits are {id: int, field: str, value: int}. Name edits use executable_text.
    Duplicate edits to a field are rejected so composition order is explicit.
    """
    if len(table) != COUNT * RECORD_SIZE:
        raise ValueError("Cards require exactly 110 eight-byte records")
    output = bytearray(table)
    seen = set()
    for edit in edits:
        card_id = _integer(edit.get("id"), "Card ID")
        field = edit.get("field")
        if not 0 <= card_id < COUNT or field not in FIELDS:
            raise ValueError("Invalid card ID or field")
        key = (card_id, field)
        if key in seen:
            raise ValueError("Duplicate card field edit")
        seen.add(key)
        value = _integer(edit.get("value"), str(field))
        if field == "element":
            valid = value in ELEMENTS
        else:
            valid = 0 <= value <= (255 if field == "power" else 10)
        if not valid:
            raise ValueError(f"Invalid {field} value: {value}")
        output[card_id * RECORD_SIZE + FIELDS.index(field)] = value
    return bytes(output), sum(a != b for a, b in zip(output, table))


def build_hext(exe: bytes, edits: list[dict]) -> str:
    """Emit only changed scalar bytes at both resolved runtime addresses.

    Other mods can change separate fields of the same card without a full
    record write undoing them. Same-field conflicts follow Hext load order.
    """
    tables = read_tables(exe)
    modified, changed = apply_edits(tables[0], edits)
    if not changed:
        return ""
    lines = ["# Triple Triad card properties: menu and minigame tables."]
    for offset, original in zip(TABLE_OFFSETS, tables):
        address = _virtual_address(exe, offset, len(original))
        for i, (before, after) in enumerate(zip(original, modified)):
            if before != after:
                lines.append(f"{address + i:X} = {after:02X}")
    return "\n".join(lines) + "\n"


def load(path: Path, names: list[str] | None = None) -> list[dict]:
    exe = Path(path).read_bytes()
    if names is None:
        names = executable_text.extract(Path(path), executable_text.BY_ID["exe_card_names"])
    return read_cards(exe, names)


def project_edits(project: Path, exe: bytes) -> list[dict]:
    manifest = Path(project) / MANIFEST
    hext = Path(project) / HEXT
    if not manifest.exists():
        if hext.exists():
            raise ValueError("Card patch exists without its editable card data")
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("version") != 1 or data.get("executable") != executable_text.SUPPORTED_EXE_SHA256:
        raise ValueError("Unsupported card project format or executable")
    edits = data.get("edits")
    if not isinstance(edits, list):
        raise ValueError("Invalid card edits")
    expected = build_hext(exe, edits)
    if not hext.is_file() or hext.read_text(encoding="utf-8") != expected:
        raise ValueError("Card patch differs from editable card data; resolve the external edit first")
    return edits


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cards-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_project(project: Path, exe: bytes, edits: list[dict]) -> dict:
    """Merge field edits, normalize baseline resets, and retain editable state.

    The generated Hext participates in runtime_layout's existing ordered Hext
    composition. Externally changed generated patches are never overwritten.
    """
    with _LOCK:
        baseline = read_tables(exe)[0]
        existing = project_edits(project, exe)
        current = apply_edits(baseline, existing)[0]
        updated, changed = apply_edits(current, edits)
        normalized = [{"id": i, "field": field, "value": updated[i * 8 + j]}
                      for i in range(COUNT) for j, field in enumerate(FIELDS)
                      if updated[i * 8 + j] != baseline[i * 8 + j]]
        manifest = {"version": 1, "executable": executable_text.SUPPORTED_EXE_SHA256,
                    "edits": normalized}
        pending = [(Path(project) / MANIFEST, (json.dumps(manifest, indent=2) + "\n").encode()),
                   (Path(project) / HEXT, build_hext(exe, normalized).encode())]
        old = [(p, p.read_bytes() if p.exists() else None) for p, _ in pending]
        try:
            for path, value in pending:
                _write(path, value)
        except Exception:
            for path, value in old:
                if value is None:
                    path.unlink(missing_ok=True)
                else:
                    _write(path, value)
            raise
        return {"saved": changed, "files": [str(p) for p, _ in pending]}


def payload(dataset: str = "current") -> dict:
    from . import paths, formats
    exe = (paths.GAME_ROOT / "FF8_EN.exe").read_bytes()
    names_source = executable_text.BY_ID["exe_card_names"]
    raw_names = formats._executable_text_msd(names_source, dataset)
    positions = [int.from_bytes(raw_names[i:i + 4], "little") for i in range(0, COUNT * 4, 4)]
    names = executable_text._read_entries(raw_names, positions, COUNT)
    rows = read_cards(exe, names)
    if dataset == "vanilla":
        edits = []
    elif dataset == "current":
        edits = project_edits(paths.PROJECT_ROOT, exe)
    else:
        root = formats._managed_root(dataset)
        if dataset.startswith("reference:"):
            reference = next((r for r in formats.reference_roots()
                              if r["id"] == dataset.partition(":")[2]), None)
            root = Path(reference["path"]) if reference else None
        if root is None:
            raise ValueError("Unknown card dataset")
        edits = project_edits(Path(root), exe)
    for edit in edits:
        rows[edit["id"]][edit["field"]] = edit["value"]
    return {"rows": rows, "elements": [{"id": key, "name": name} for key, name in ELEMENTS.items()],
            "source": "FF8_EN.exe", "count": COUNT}


def save(edits: list[dict]) -> dict:
    from . import paths
    return save_project(paths.PROJECT_ROOT, (paths.GAME_ROOT / "FF8_EN.exe").read_bytes(), edits)
