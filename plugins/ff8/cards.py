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

from . import executable_text, project_files

COUNT = 110
RECORD_SIZE = 8
TABLE_OFFSETS = (0x796508, 0x874D00)
FIELDS = ("top", "bottom", "left", "right", "element", "power")
OWNER_FIELD = "startingOwner"
RARE_START = 77
INITIALIZER = 0x8DFF20
INITIALIZER_SIZE = 80
DEFAULT_OWNERS = bytes(range(200, 233))
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
    return [dict(id=i, name=names[i], **({OWNER_FIELD: DEFAULT_OWNERS[i - RARE_START]}
                                      if i >= RARE_START else {}),
                 **dict(zip(FIELDS, table[i * 8:i * 8 + 6])))
            for i in range(COUNT)]


def split_edits(edits: list[dict]) -> tuple[list[dict], list[dict]]:
    properties, owners = [], []
    for edit in edits:
        (owners if edit.get("field") == OWNER_FIELD else properties).append(edit)
    return properties, owners


def apply_owner_edits(owners: bytes, edits: list[dict]) -> tuple[bytes, int]:
    if len(owners) != COUNT - RARE_START:
        raise ValueError("Starting ownership requires all 33 rare cards")
    result = bytearray(owners)
    seen = set()
    for edit in edits:
        card_id = _integer(edit.get("id"), "Rare card ID")
        value = _integer(edit.get("value"), "Starting deck")
        if (edit.get("field") != OWNER_FIELD or not RARE_START <= card_id < COUNT
                or not 0 <= value <= 239):
            raise ValueError("Invalid rare card or starting opponent deck")
        if card_id in seen:
            raise ValueError("Duplicate starting deck edit")
        seen.add(card_id)
        result[card_id - RARE_START] = value
    return bytes(result), sum(a != b for a, b in zip(result, owners))


def owner_initializer(owners: bytes) -> bytes:
    """Authored replacement within the original function's 80-byte footprint.

    Clear inventory and seen flags, preserve unrelated flags, initialize RNG,
    then copy the complete starting-owner map. No code cave or driver needed.
    """
    if len(owners) != 33:
        raise ValueError("Starting ownership requires all 33 rare cards")
    code = bytes.fromhex(
        "56 57 BF 38 EF CF 01 31 C0 6A 1B 59 F3 AB 66 AB "
        "89 07 88 47 04 80 67 05 FE C7 47 0E 01 00 00 00 BE"
    ) + struct.pack("<I", INITIALIZER + 47) + bytes.fromhex(
        "83 EF 21 B1 21 F3 A4 5F 5E C3")
    assert len(code) == 47
    return code + owners


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
    """Emit changed properties and, when needed, the full starting-owner map.

    Other mods can change separate fields of the same card without a full
    record write undoing them. Same-field conflicts follow Hext load order.
    Starting ownership uses one complete initializer, so the last map wins.
    """
    tables = read_tables(exe)
    property_edits, owner_edits = split_edits(edits)
    modified, changed = apply_edits(tables[0], property_edits)
    owners, owner_changes = apply_owner_edits(DEFAULT_OWNERS, owner_edits)
    if not changed and not owner_changes:
        return ""
    lines = ["# Triple Triad card properties: menu and minigame tables."]
    for offset, original in zip(TABLE_OFFSETS, tables):
        address = _virtual_address(exe, offset, len(original))
        for i, (before, after) in enumerate(zip(original, modified)):
            if before != after:
                lines.append(f"{address + i:X} = {after:02X}")
    if owner_changes:
        # Full executable hash validation above guards the overwritten function.
        # Each mod owns a complete map; higher-priority maps replace lower ones.
        lines.append("# Starting rare-card map: new games only; last map in load order wins.")
        patch = owner_initializer(owners)
        assert len(patch) == INITIALIZER_SIZE
        lines.append(f"{INITIALIZER:X} = {patch.hex(' ').upper()}")
    return "\n".join(lines) + "\n"


def load(path: Path, names: list[str] | None = None) -> list[dict]:
    exe = Path(path).read_bytes()
    if names is None:
        names = executable_text.extract(Path(path), executable_text.BY_ID["exe_card_names"])
    return read_cards(exe, names)


def project_edits(project: Path, exe: bytes) -> list[dict]:
    with _LOCK:
        if (Path(project) / ".cards-recovery").exists():
            raise OSError(f"Card project has pending recovery at {Path(project) / '.cards-recovery'}")
        return _project_edits_locked(project, exe)


def _project_edits_locked(project: Path, exe: bytes) -> list[dict]:
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


def _commit_project_files(project: Path, pending: list, original: list) -> None:
    """Keep one bounded recovery set until both files commit or restore."""
    project_files.commit_files(project, pending, original, label='Card',
                               recovery_name='.cards-recovery', write=_write)


def _project_snapshot(path: Path) -> bytes | None:
    if not path.exists():
        return None
    # Normalized edits contain at most 693 scalar fields. Do not copy a large,
    # unrelated file into recovery merely because it has a generated filename.
    limit = 1024 * 1024
    if path.stat().st_size > limit:
        raise ValueError(f"Card project file exceeds the 1 MiB limit: {path}")
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise ValueError(f"Card project file exceeds the 1 MiB limit: {path}")
    return value


def save_project(project: Path, exe: bytes, edits: list[dict]) -> dict:
    """Merge field edits, normalize baseline resets, and retain editable state.

    The generated Hext participates in runtime_layout's existing ordered Hext
    composition. Externally changed generated patches are never overwritten.
    """
    with _LOCK:
        project = Path(project)
        if (project / ".cards-recovery").exists():
            raise OSError(f"Card save has pending recovery at {project / '.cards-recovery'}; resolve it before saving again")
        targets = [project / MANIFEST, project / HEXT]
        old = [(p, _project_snapshot(p)) for p in targets]
        baseline = read_tables(exe)[0]
        existing = project_edits(project, exe)
        existing_properties, existing_owners = split_edits(existing)
        property_edits, owner_edits = split_edits(edits)
        current = apply_edits(baseline, existing_properties)[0]
        current_owners = apply_owner_edits(DEFAULT_OWNERS, existing_owners)[0]
        updated, changed = apply_edits(current, property_edits)
        updated_owners, owner_changes = apply_owner_edits(current_owners, owner_edits)
        normalized = [{"id": i, "field": field, "value": updated[i * 8 + j]}
                      for i in range(COUNT) for j, field in enumerate(FIELDS)
                      if updated[i * 8 + j] != baseline[i * 8 + j]]
        normalized.extend({"id": i + RARE_START, "field": OWNER_FIELD, "value": value}
                          for i, value in enumerate(updated_owners) if value != DEFAULT_OWNERS[i])
        manifest = {"version": 1, "executable": executable_text.SUPPORTED_EXE_SHA256,
                    "edits": normalized}
        pending = [(Path(project) / MANIFEST, (json.dumps(manifest, indent=2) + "\n").encode()),
                   (Path(project) / HEXT, build_hext(exe, normalized).encode())]
        _commit_project_files(project, pending, old)
        return {"saved": changed + owner_changes, "files": [str(p) for p, _ in pending]}


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
