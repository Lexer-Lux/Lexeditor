"""Fail-closed FF8 field data, geometry, script, and background editor.

Archive nesting follows Deling ``FieldArchivePC::open`` and ``FieldPC::open``.
The one editable path follows FF8 Ultimate Editor's ``CCGroup/jsmcardgame.py``:
seven fixed-size push instructions immediately before field opcode 0x13A.
The fixed-size INF gateway and trigger records follow Deling's ``InfFile`` and
OpenVIII's independent ``INF`` reader.  Writes patch only selected scalar
fields in the original INF variant; all unknown bytes remain unchanged.
Field dialogue follows Deling's ``MsdFile`` and OpenVIII's independent MSD
reader.  Its writer rebuilds only the selected map's offset table and payload.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path, PureWindowsPath
import shutil
import struct
import tempfile

from . import (field_background, field_dialogue, field_encounters, field_scripts,
               field_walkmesh, paths, runtime_layout)
from .fs_archive import FsArchive
from .vendor.ff8ue.lzs import Lzs


FIELD_PREFIX = "field"
BASELINE_SUBDIR = Path("field/mapdata")
DIRECT_SUBDIR = Path("field/mapdata")
CARDGAME_DWORD = 0x0000013A
PARAM_NAMES = ("Deck ID", "Game rules", "Trade rules", "Rare card chance",
               "AI search profile", "AI strategy profile", "Allowed card levels")
LITERAL_OPCODE = 0x07
VARIABLE_OPCODES = {0x0A, 0x0C, 0x0E, 0x10, 0x11, 0x12}
EDITABLE_OPCODES = {LITERAL_OPCODE, *VARIABLE_OPCODES}
VERTEX_AXES = ("x", "y", "z")


def _prefix() -> Path:
    return paths.GAME_ROOT / "Data" / "lang-en" / FIELD_PREFIX


def _fingerprint(prefix: Path | None = None) -> dict:
    prefix = prefix or _prefix()
    return {suffix: {"size": prefix.with_suffix(suffix).stat().st_size,
                     "mtimeNs": prefix.with_suffix(suffix).stat().st_mtime_ns}
            for suffix in (".fs", ".fi", ".fl")}


def _memory_entries(fi: bytes, fl: bytes) -> list[dict]:
    names = fl.decode("utf-8", errors="strict").splitlines()
    if len(fi) != len(names) * 12:
        raise ValueError("Nested field FI and FL entry counts differ")
    entries = []
    for index, name in enumerate(names):
        unpacked, offset, compression = struct.unpack_from("<III", fi, index * 12)
        if compression not in (0, 1):
            raise ValueError(f"Unsupported nested field compression {compression}")
        entries.append({"name": name, "basename": PureWindowsPath(name).name.casefold(),
                        "unpacked": unpacked, "offset": offset,
                        "compressed": bool(compression)})
    return entries


def _memory_extract(fs: bytes, entries: list[dict], basename: str) -> bytes:
    matches = [entry for entry in entries if entry["basename"] == basename.casefold()]
    if len(matches) != 1:
        raise KeyError(f"Expected one {basename} in nested field archive; found {len(matches)}")
    entry = matches[0]
    later = [candidate["offset"] for candidate in entries if candidate["offset"] > entry["offset"]]
    end = min(later) if later else len(fs)
    if not 0 <= entry["offset"] < end <= len(fs):
        raise ValueError(f"Invalid nested field extent for {basename}")
    if entry["compressed"]:
        if end < entry["offset"] + 4:
            raise ValueError(f"Missing nested compressed length for {basename}")
        stored = struct.unpack_from("<I", fs, entry["offset"])[0]
        if stored > end - entry["offset"] - 4:
            raise ValueError(f"Nested stored size exceeds extent for {basename}")
        data = bytes(Lzs().decode(fs[entry["offset"] + 4:entry["offset"] + 4 + stored]))
    else:
        data = fs[entry["offset"]:entry["offset"] + entry["unpacked"]]
    if len(data) != entry["unpacked"]:
        raise ValueError(f"{basename} decoded to {len(data)} bytes; expected {entry['unpacked']}")
    return data


def _outer_groups(archive: FsArchive) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for entry in archive.entries:
        path = PureWindowsPath(entry.name)
        parts = [part.casefold() for part in path.parts]
        if "mapdata" not in parts:
            continue
        position = parts.index("mapdata")
        tail = path.parts[position + 1:]
        if len(tail) != 2 or path.suffix.casefold() not in {".fs", ".fi", ".fl"}:
            continue
        subdir, filename = tail
        name = PureWindowsPath(filename).stem
        key = f"{subdir.casefold()}/{name.casefold()}"
        group = groups.setdefault(key, {"key": key, "name": name,
                                        "group": subdir.casefold(), "entries": {}})
        suffix = path.suffix.casefold()
        if suffix in group["entries"]:
            raise ValueError(f"Duplicate {suffix} for field map {key}")
        group["entries"][suffix] = entry
    incomplete = [key for key, group in groups.items()
                  if set(group["entries"]) != {".fs", ".fi", ".fl"}]
    if incomplete:
        raise ValueError(f"Incomplete field archive triplet: {incomplete[0]}")
    return groups


def _maplist(archive: FsArchive) -> list[str]:
    fi = archive.extract(archive.find("mapdata.fi"))
    fl = archive.extract(archive.find("mapdata.fl"))
    fs = archive.extract(archive.find("mapdata.fs"))
    entries = _memory_entries(fi, fl)
    return _memory_extract(fs, entries, "maplist").decode("ascii", errors="strict").splitlines()


def ensure_index() -> dict:
    destination = paths.BASELINE_ROOT / "field/index.json"
    fingerprint = _fingerprint()
    if destination.is_file():
        try:
            cached = json.loads(destination.read_text(encoding="utf-8"))
            rows = cached.get("rows")
            if (cached.get("source") == fingerprint and isinstance(rows, list) and rows and
                    all(isinstance(row, dict) and isinstance(row.get("id"), int) and
                        isinstance(row.get("key"), str) and "/" in row["key"]
                        for row in rows)):
                return cached
        except (OSError, ValueError, TypeError):
            pass
    archive = FsArchive(_prefix())
    groups = _outer_groups(archive)
    maplist = _maplist(archive)
    listed_ids = {name.casefold(): index for index, name in enumerate(maplist)}
    ordered = sorted(groups.values(), key=lambda group: (
        listed_ids.get(group["name"].casefold(), 1_000_000), group["key"]))
    rows = [{"id": index, "key": group["key"], "name": group["name"],
             "group": group["group"], "mapId": listed_ids.get(group["name"].casefold()),
             "listed": group["name"].casefold() in listed_ids}
            for index, group in enumerate(ordered)]
    result = {"source": fingerprint, "rows": rows, "listedCount": len(maplist)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".field-index-", suffix=".json",
                                         dir=destination.parent)
    try:
        with open(handle, "w", encoding="utf-8", closefd=True) as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        Path(temporary).replace(destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return result


def _map_row(key: str) -> dict:
    match = next((row for row in ensure_index()["rows"] if row["key"] == key), None)
    if match is None:
        raise ValueError(f"Unknown field map: {key}")
    return match


def ensure_map_baseline(key: str) -> tuple[Path | None, Path | None, Path | None]:
    row = _map_row(key)
    directory = paths.BASELINE_ROOT / BASELINE_SUBDIR / row["group"] / row["name"]
    jsm_path, sym_path = directory / f"{row['name']}.jsm", directory / f"{row['name']}.sym"
    inf_path = directory / f"{row['name']}.inf"
    metadata = directory / ".source.json"
    fingerprint = _fingerprint()
    if metadata.is_file():
        try:
            cached = json.loads(metadata.read_text(encoding="utf-8"))
            assets = cached.get("assets", [])
            if (cached.get("version") == 5 and cached.get("source") == fingerprint and
                    all(name in {"jsm", "sym", "inf", "msd", "id", "map", "mim"}
                        or name in {"mrt", "rat"} for name in assets) and
                    all((directory / f"{row['name']}.{name}").is_file()
                        for name in assets)):
                if "jsm" in assets and "sym" in assets:
                    _parse_card_players(jsm_path.read_bytes(), sym_path.read_bytes())
                elif "jsm" in assets or "sym" in assets:
                    raise ValueError("Field map has an incomplete JSM/SYM pair")
                if "inf" in assets:
                    _parse_inf(inf_path.read_bytes())
                if "msd" in assets:
                    field_dialogue.read((directory / f"{row['name']}.msd").read_bytes())
                if "id" in assets:
                    field_walkmesh.read((directory / f"{row['name']}.id").read_bytes())
                if ("map" in assets) != ("mim" in assets):
                    raise ValueError("Field map has an incomplete MAP/MIM background pair")
                if "map" in assets:
                    field_background.read(
                        (directory / f"{row['name']}.map").read_bytes(),
                        (directory / f"{row['name']}.mim").read_bytes())
                if ("mrt" in assets) != ("rat" in assets):
                    raise ValueError("Field map has an incomplete MRT/RAT encounter pair")
                if "mrt" in assets:
                    field_encounters.read_mrt(
                        (directory / f"{row['name']}.mrt").read_bytes())
                    rate = field_encounters.read_rat(
                        (directory / f"{row['name']}.rat").read_bytes())
                    if not rate["canonical"]:
                        raise ValueError("Field RAT does not contain four matching rate bytes")
                return (jsm_path if "jsm" in assets else None,
                        sym_path if "sym" in assets else None,
                        inf_path if "inf" in assets else None)
        except (OSError, ValueError, TypeError):
            pass
    archive = FsArchive(_prefix())
    group = _outer_groups(archive)[key]
    fs = archive.extract(group["entries"][".fs"])
    fi = archive.extract(group["entries"][".fi"])
    fl = archive.extract(group["entries"][".fl"])
    entries = _memory_entries(fi, fl)
    by_name = {entry["basename"]: entry for entry in entries}
    extracted = {}
    for extension in ("jsm", "sym", "inf", "msd", "id", "map", "mim", "mrt", "rat"):
        basename = f"{row['name']}.{extension}".casefold()
        if basename in by_name:
            extracted[extension] = _memory_extract(fs, entries, basename)
    if ("jsm" in extracted) != ("sym" in extracted):
        raise ValueError("Field map has an incomplete JSM/SYM pair")
    if "jsm" in extracted:
        _parse_card_players(extracted["jsm"], extracted["sym"])
    if "inf" in extracted:
        _parse_inf(extracted["inf"])
    if "msd" in extracted:
        field_dialogue.read(extracted["msd"])
    if "id" in extracted:
        field_walkmesh.read(extracted["id"])
    if ("map" in extracted) != ("mim" in extracted):
        raise ValueError("Field map has an incomplete MAP/MIM background pair")
    if "map" in extracted:
        field_background.read(extracted["map"], extracted["mim"])
    if ("mrt" in extracted) != ("rat" in extracted):
        raise ValueError("Field map has an incomplete MRT/RAT encounter pair")
    if "mrt" in extracted:
        field_encounters.read_mrt(extracted["mrt"])
        rate = field_encounters.read_rat(extracted["rat"])
        if not rate["canonical"]:
            raise ValueError("Field RAT does not contain four matching rate bytes")
    directory.mkdir(parents=True, exist_ok=True)
    for extension, destination in (("jsm", jsm_path), ("sym", sym_path), ("inf", inf_path),
                                   ("msd", directory / f"{row['name']}.msd"),
                                   ("id", directory / f"{row['name']}.id"),
                                   ("map", directory / f"{row['name']}.map"),
                                   ("mim", directory / f"{row['name']}.mim"),
                                   ("mrt", directory / f"{row['name']}.mrt"),
                                   ("rat", directory / f"{row['name']}.rat")):
        destination.unlink(missing_ok=True)
        if extension in extracted:
            destination.write_bytes(extracted[extension])
    metadata.write_text(json.dumps({"version": 5, "source": fingerprint,
                                    "assets": sorted(extracted)}, indent=2) + "\n",
                        encoding="utf-8")
    return (jsm_path if "jsm" in extracted else None,
            sym_path if "sym" in extracted else None,
            inf_path if "inf" in extracted else None)


def _inf_layout(size: int) -> dict:
    """Return offsets proved by Deling InfFile::open and OpenVIII INF.ReadData."""
    layouts = {
        676: {"variant": 0, "gatewayOffset": 100, "gatewaySize": 32,
              "triggerOffset": 484},
        672: {"variant": 1, "gatewayOffset": 96, "gatewaySize": 32,
              "triggerOffset": 480},
        576: {"variant": 2, "gatewayOffset": 96, "gatewaySize": 24,
              "triggerOffset": 384},
        504: {"variant": 3, "gatewayOffset": 24, "gatewaySize": 24,
              "triggerOffset": 312},
    }
    try:
        return layouts[size]
    except KeyError as error:
        raise ValueError(f"Unsupported field INF size: {size}") from error


def _vertex(raw: bytes, offset: int) -> dict:
    x, y, z = struct.unpack_from("<hhh", raw, offset)
    return {"x": x, "y": y, "z": z, "offset": offset}


def _parse_inf(raw: bytes) -> dict:
    layout = _inf_layout(len(raw))
    gateways = []
    for slot in range(12):
        offset = layout["gatewayOffset"] + slot * layout["gatewaySize"]
        field_id = struct.unpack_from("<H", raw, offset + 18)[0]
        gateways.append({
            "id": slot, "active": field_id != 0x7FFF, "fieldId": field_id,
            "exitA": _vertex(raw, offset), "exitB": _vertex(raw, offset + 6),
            "destination": _vertex(raw, offset + 12), "offset": offset,
        })
    triggers = []
    for slot in range(12):
        offset = layout["triggerOffset"] + slot * 16
        door_id = raw[offset + 12]
        triggers.append({
            "id": slot, "active": door_id != 0xFF, "doorId": door_id,
            "lineA": _vertex(raw, offset), "lineB": _vertex(raw, offset + 6),
            "offset": offset,
        })
    return {"variant": layout["variant"], "size": len(raw),
            "gateways": gateways, "triggers": triggers}


def _script_names(sym: bytes, entity_count: int) -> list[tuple[str, str]]:
    lines = [line.strip() for line in sym.decode("ascii", errors="replace").splitlines()
             if line.strip()]
    result = []
    for line in lines[entity_count:]:
        result.append(tuple(line.split("::", 1)) if "::" in line else (line, "init"))
    return result


def _parse_card_players(jsm: bytes, sym: bytes) -> list[dict]:
    if len(jsm) < 8:
        raise ValueError("Field JSM is too small")
    entity_count = sum(jsm[:4])
    table_offset, script_offset = struct.unpack_from("<HH", jsm, 4)
    if table_offset > script_offset or script_offset > len(jsm) or (script_offset - table_offset) % 2:
        raise ValueError("Field JSM has an invalid script table")
    positions = [(struct.unpack_from("<H", jsm, offset)[0] & 0x7FFF) * 4
                 for offset in range(table_offset, script_offset, 2)]
    names = _script_names(sym, entity_count)
    script_size = len(jsm) - script_offset
    players = []
    for relative in range(0, script_size - 3, 4):
        if struct.unpack_from("<I", jsm, script_offset + relative)[0] != CARDGAME_DWORD or relative < 28:
            continue
        script_index = next((index for index, start in enumerate(positions)
                             if start <= relative < (positions[index + 1]
                                if index + 1 < len(positions) else script_size)), None)
        entity, script = names[script_index] if script_index is not None and script_index < len(names) \
            else ("entity?", f"offset 0x{relative:X}")
        params = []
        for index, name in enumerate(PARAM_NAMES):
            offset = script_offset + relative - (7 - index) * 4
            word = struct.unpack_from("<I", jsm, offset)[0]
            opcode, value = word >> 24, word & 0xFFFFFF
            params.append({"id": index, "name": name, "offset": offset,
                           "opcode": opcode, "value": value,
                           "mode": "literal" if opcode == LITERAL_OPCODE else
                                   "variable" if opcode in VARIABLE_OPCODES else "unsupported",
                           "editable": opcode in EDITABLE_OPCODES})
        players.append({"id": len(players), "entity": entity, "script": script,
                        "offset": script_offset + relative, "params": params,
                        "editable": all(param["editable"] for param in params)})
    return players


def _source_paths(key: str, dataset: str) -> tuple[Path | None, Path | None]:
    baseline_jsm, baseline_sym, _ = ensure_map_baseline(key)
    row = _map_row(key)
    relative = DIRECT_SUBDIR / row["group"] / row["name"] / f"{row['name']}.jsm"
    if dataset == "vanilla":
        return baseline_jsm, baseline_sym
    if dataset == "current":
        override = paths.DIRECT_ROOT / relative
        return (override if override.is_file() else baseline_jsm), baseline_sym
    if dataset.startswith("reference:"):
        reference = paths.PROJECT_ROOT / "references" / dataset.partition(":")[2]
        candidates = (reference / "direct" / relative, reference / relative)
        match = next((candidate for candidate in candidates if candidate.is_file()), None)
        return match or baseline_jsm, baseline_sym
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        candidates = (root / "direct" / relative, root / relative)
        match = next((candidate for candidate in candidates if candidate.is_file()), baseline_jsm)
        return match, baseline_sym
    raise ValueError(f"Unknown dataset: {dataset}")


def _inf_source_path(key: str, dataset: str) -> Path | None:
    _, _, baseline = ensure_map_baseline(key)
    row = _map_row(key)
    relative = DIRECT_SUBDIR / row["group"] / row["name"] / f"{row['name']}.inf"
    if dataset == "vanilla":
        return baseline
    if dataset == "current":
        override = paths.DIRECT_ROOT / relative
        return override if override.is_file() else baseline
    if dataset.startswith("reference:"):
        reference = paths.PROJECT_ROOT / "references" / dataset.partition(":")[2]
        match = next((candidate for candidate in
                      (reference / "direct" / relative, reference / relative)
                      if candidate.is_file()), None)
        return match or baseline
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        return next((candidate for candidate in
                     (root / "direct" / relative, root / relative)
                     if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def _dialogue_source_path(key: str, dataset: str) -> Path | None:
    ensure_map_baseline(key)
    row = _map_row(key)
    baseline = (paths.BASELINE_ROOT / BASELINE_SUBDIR / row["group"] / row["name"] /
                f"{row['name']}.msd")
    baseline = baseline if baseline.is_file() else None
    relative = DIRECT_SUBDIR / row["group"] / row["name"] / f"{row['name']}.msd"
    if dataset == "vanilla":
        return baseline
    if dataset == "current":
        override = paths.DIRECT_ROOT / relative
        return override if override.is_file() else baseline
    if dataset.startswith("reference:"):
        reference = paths.PROJECT_ROOT / "references" / dataset.partition(":")[2]
        return next((candidate for candidate in
                     (reference / "direct" / relative, reference / relative)
                     if candidate.is_file()), baseline)
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        return next((candidate for candidate in
                     (root / "direct" / relative, root / relative)
                     if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def _walkmesh_source_path(key: str, dataset: str) -> Path | None:
    ensure_map_baseline(key)
    row = _map_row(key)
    baseline = (paths.BASELINE_ROOT / BASELINE_SUBDIR / row["group"] / row["name"] /
                f"{row['name']}.id")
    baseline = baseline if baseline.is_file() else None
    relative = DIRECT_SUBDIR / row["group"] / row["name"] / f"{row['name']}.id"
    if dataset == "vanilla":
        return baseline
    if dataset == "current":
        override = paths.DIRECT_ROOT / relative
        return override if override.is_file() else baseline
    if dataset.startswith("reference:"):
        reference = paths.PROJECT_ROOT / "references" / dataset.partition(":")[2]
        return next((candidate for candidate in
                     (reference / "direct" / relative, reference / relative)
                     if candidate.is_file()), baseline)
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        return next((candidate for candidate in
                     (root / "direct" / relative, root / relative)
                     if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def _background_source_paths(key: str, dataset: str) -> tuple[Path | None, Path | None]:
    """Resolve a complete MAP/MIM view while allowing either file to be overridden."""
    ensure_map_baseline(key)
    row = _map_row(key)
    directory = paths.BASELINE_ROOT / BASELINE_SUBDIR / row["group"] / row["name"]
    baseline_map = directory / f"{row['name']}.map"
    baseline_mim = directory / f"{row['name']}.mim"
    if not baseline_map.is_file() and not baseline_mim.is_file():
        return None, None
    if not baseline_map.is_file() or not baseline_mim.is_file():
        raise ValueError(f"Field map {key} has an incomplete baseline MAP/MIM pair")
    relative_directory = DIRECT_SUBDIR / row["group"] / row["name"]
    if dataset == "vanilla":
        return baseline_map, baseline_mim
    if dataset == "current":
        roots = (paths.DIRECT_ROOT,)
    elif dataset.startswith("reference:"):
        reference = paths.PROJECT_ROOT / "references" / dataset.partition(":")[2]
        roots = (reference / "direct", reference)
    elif dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        roots = (root / "direct", root)
    else:
        raise ValueError(f"Unknown dataset: {dataset}")
    resolved = []
    for extension, baseline in (("map", baseline_map), ("mim", baseline_mim)):
        relative = relative_directory / f"{row['name']}.{extension}"
        resolved.append(next((root / relative for root in roots
                              if (root / relative).is_file()), baseline))
    return resolved[0], resolved[1]


def _encounter_source_paths(key: str, dataset: str) -> tuple[Path | None, Path | None]:
    """Resolve the selected field's complete MRT/RAT encounter pair."""
    ensure_map_baseline(key)
    row = _map_row(key)
    directory = paths.BASELINE_ROOT / BASELINE_SUBDIR / row["group"] / row["name"]
    baseline_mrt = directory / f"{row['name']}.mrt"
    baseline_rat = directory / f"{row['name']}.rat"
    if not baseline_mrt.is_file() and not baseline_rat.is_file():
        return None, None
    if not baseline_mrt.is_file() or not baseline_rat.is_file():
        raise ValueError(f"Field map {key} has an incomplete baseline MRT/RAT pair")
    relative_directory = DIRECT_SUBDIR / row["group"] / row["name"]
    if dataset == "vanilla":
        return baseline_mrt, baseline_rat
    if dataset == "current":
        roots = (paths.DIRECT_ROOT,)
    elif dataset.startswith("reference:"):
        reference = paths.PROJECT_ROOT / "references" / dataset.partition(":")[2]
        roots = (reference / "direct", reference)
    elif dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        roots = (root / "direct", root)
    else:
        raise ValueError(f"Unknown dataset: {dataset}")
    resolved = []
    for extension, baseline in (("mrt", baseline_mrt), ("rat", baseline_rat)):
        relative = relative_directory / f"{row['name']}.{extension}"
        resolved.append(next((root / relative for root in roots
                              if (root / relative).is_file()), baseline))
    return resolved[0], resolved[1]


def index_rows(dataset: str = "current") -> dict:
    # Indexing is independent of mod contents; dataset is accepted for the same
    # API contract as other tabs and validated here to fail closed.
    if dataset not in {"current", "vanilla"} and not dataset.startswith(("reference:", "mod:")):
        raise ValueError(f"Unknown dataset: {dataset}")
    result = ensure_index()
    return {"rows": result["rows"], "listedCount": result["listedCount"],
            "source": str(_prefix().with_suffix(".fs"))}


def map_rows(key: str, dataset: str = "current") -> dict:
    row = _map_row(key)
    jsm, sym = _source_paths(key, dataset)
    inf_path = _inf_source_path(key, dataset)
    raw = jsm.read_bytes() if jsm is not None else None
    inf_raw = inf_path.read_bytes() if inf_path is not None else None
    dialogue_path = _dialogue_source_path(key, dataset)
    dialogue_raw = dialogue_path.read_bytes() if dialogue_path is not None else None
    walkmesh_path = _walkmesh_source_path(key, dataset)
    walkmesh_raw = walkmesh_path.read_bytes() if walkmesh_path is not None else None
    background_map_path, background_mim_path = _background_source_paths(key, dataset)
    background_map_raw = (background_map_path.read_bytes()
                          if background_map_path is not None else None)
    background_mim_raw = (background_mim_path.read_bytes()
                          if background_mim_path is not None else None)
    encounter_mrt_path, encounter_rat_path = _encounter_source_paths(key, dataset)
    encounter_mrt_raw = (encounter_mrt_path.read_bytes()
                         if encounter_mrt_path is not None else None)
    encounter_rat_raw = (encounter_rat_path.read_bytes()
                         if encounter_rat_path is not None else None)
    entrances = (_parse_inf(inf_raw) if inf_raw is not None else
                 {"variant": None, "size": 0, "gateways": [], "triggers": []})
    script_error = None
    try:
        scripts = field_scripts.read(raw, sym.read_bytes()) if raw is not None and sym is not None else {
            "header": None, "groups": [], "methods": [],
            "opcodeCount": len(field_scripts.OPCODE_NAMES)}
    except ValueError as error:
        script_error = str(error)
        scripts = {"header": None, "groups": [], "methods": [],
                   "opcodeCount": len(field_scripts.OPCODE_NAMES), "error": script_error}
    for method in scripts["methods"]:
        method.pop("raw", None)
    walkmesh_error = None
    try:
        walkmesh = (field_walkmesh.read(walkmesh_raw) if walkmesh_raw is not None else
                    {"triangleCount": 0, "triangles": [], "trailingUnknown": None})
    except ValueError as error:
        walkmesh_error = str(error)
        walkmesh = {"triangleCount": 0, "triangles": [], "trailingUnknown": None,
                    "error": walkmesh_error}
    for triangle in walkmesh["triangles"]:
        for vertex in triangle["vertices"]:
            vertex.pop("reserved", None)
    background_error = None
    try:
        background = (field_background.read(background_map_raw, background_mim_raw)
                      if background_map_raw is not None and background_mim_raw is not None
                      else {"variant": None, "tileSize": 0, "tileCount": 0, "tiles": [],
                            "layers": [], "parameterStates": [], "bounds": {}})
    except ValueError as error:
        background_error = str(error)
        background = {"variant": None, "tileSize": 0, "tileCount": 0, "tiles": [],
                      "layers": [], "parameterStates": [], "bounds": {},
                      "error": background_error}
    for tile in background["tiles"]:
        tile.pop("offset", None)
    background["editableFields"] = (list(field_background.editable_fields(
        background["variant"])) if background["variant"] else [])
    if encounter_mrt_raw is not None and encounter_rat_raw is not None:
        encounter_rate = field_encounters.read_rat(encounter_rat_raw)
        if not encounter_rate["canonical"]:
            raise ValueError(f"Field map {key} has a noncanonical RAT encounter rate")
        random_encounters = {
            "formations": field_encounters.read_mrt(encounter_mrt_raw)["formations"],
            "rate": encounter_rate["rate"],
        }
    else:
        random_encounters = {"formations": [], "rate": None}
    return {**row, "players": _parse_card_players(raw, sym.read_bytes())
            if raw is not None and sym is not None else [],
            "scripts": scripts,
            "entrances": entrances,
            "dialogue": field_dialogue.read(dialogue_raw)["lines"]
            if dialogue_raw is not None else [],
            "source": str(jsm) if jsm is not None else None,
            "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else None,
            "infSource": str(inf_path) if inf_path is not None else None,
            "infSha256": hashlib.sha256(inf_raw).hexdigest() if inf_raw is not None else None,
            "dialogueSource": str(dialogue_path) if dialogue_path is not None else None,
            "dialogueSha256": hashlib.sha256(dialogue_raw).hexdigest()
            if dialogue_raw is not None else None,
            "walkmesh": walkmesh,
            "walkmeshSource": str(walkmesh_path) if walkmesh_path is not None else None,
             "walkmeshSha256": hashlib.sha256(walkmesh_raw).hexdigest()
             if walkmesh_raw is not None else None,
            "background": background,
            "backgroundMapSource": (str(background_map_path)
                                    if background_map_path is not None else None),
            "backgroundMimSource": (str(background_mim_path)
                                    if background_mim_path is not None else None),
            "backgroundMapSha256": (hashlib.sha256(background_map_raw).hexdigest()
                                    if background_map_raw is not None else None),
            "backgroundMimSha256": (hashlib.sha256(background_mim_raw).hexdigest()
                                    if background_mim_raw is not None else None),
            "randomEncounters": random_encounters,
            "encounterMrtSource": (str(encounter_mrt_path)
                                   if encounter_mrt_path is not None else None),
            "encounterRatSource": (str(encounter_rat_path)
                                   if encounter_rat_path is not None else None),
            "encounterMrtSha256": (hashlib.sha256(encounter_mrt_raw).hexdigest()
                                   if encounter_mrt_raw is not None else None),
            "encounterRatSha256": (hashlib.sha256(encounter_rat_raw).hexdigest()
                                   if encounter_rat_raw is not None else None),
            "unsupported": (["General JSM instructions: " + script_error]
                             if script_error else []) +
                            (["Walkmesh: " + walkmesh_error]
                             if walkmesh_error else []) +
                            (["Background: " + background_error]
                             if background_error else []) +
                            ["Models", "Media"]}


def background_png(key: str, dataset: str = "current", edits: list[dict] | None = None,
                   active_states: list[dict] | None = None,
                   enabled_layers: list[int] | None = None,
                   hide_background: bool = False,
                   highlight_tile: int | None = None) -> bytes:
    map_path, mim_path = _background_source_paths(key, dataset)
    if map_path is None or mim_path is None:
        raise ValueError(f"Field map {key} has no background")
    map_raw, mim_raw = map_path.read_bytes(), mim_path.read_bytes()
    normalized = []
    for edit in edits or []:
        if not isinstance(edit, dict):
            raise ValueError("Field background preview edit must be an object")
        normalized.append({name: value for name, value in edit.items()})
    if normalized:
        map_raw, _ = field_background.apply_edits(map_raw, mim_raw, normalized)
    states = (None if active_states is None else
              {(int(entry["parameter"]), int(entry["state"])) for entry in active_states})
    layers = None if enabled_layers is None else {int(value) for value in enabled_layers}
    return field_background.render_png(
        map_raw, mim_raw, active_states=states, enabled_layers=layers,
        hide_background=hide_background, highlight_tile=highlight_tile)


def _write_atomic(destination: Path, raw: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(destination, destination.with_name(f"{destination.name}.{stamp}.bak"))
    handle, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp",
                                         dir=destination.parent)
    try:
        with open(handle, "wb", closefd=True) as stream:
            stream.write(raw)
        Path(temporary).replace(destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _edit_inf_bytes(source: bytes, edits: list[dict]) -> bytes:
    raw = bytearray(source)
    parsed = _parse_inf(raw)
    seen = set()
    scalar_offsets: dict[tuple, tuple[int, str, int, int]] = {}
    for gateway in parsed["gateways"]:
        scalar_offsets[("gateway", gateway["id"], "fieldId")] = (
            gateway["offset"] + 18, "H", 0, 0x7FFF)
        for point in ("exitA", "exitB", "destination"):
            for axis_index, axis in enumerate(VERTEX_AXES):
                scalar_offsets[("gateway", gateway["id"], point, axis)] = (
                    gateway[point]["offset"] + axis_index * 2, "h", -32768, 32767)
    for trigger in parsed["triggers"]:
        scalar_offsets[("trigger", trigger["id"], "doorId")] = (
            trigger["offset"] + 12, "B", 0, 255)
        for point in ("lineA", "lineB"):
            for axis_index, axis in enumerate(VERTEX_AXES):
                scalar_offsets[("trigger", trigger["id"], point, axis)] = (
                    trigger[point]["offset"] + axis_index * 2, "h", -32768, 32767)
    for edit in edits:
        kind = str(edit.get("kind", ""))
        slot = int(edit.get("slot", -1))
        field = str(edit.get("field", ""))
        identity = (kind, slot, field) if field in {"fieldId", "doorId"} else (
            kind, slot, field, str(edit.get("axis", "")))
        if identity in seen or identity not in scalar_offsets:
            raise ValueError("Invalid or duplicate field entrance edit")
        seen.add(identity)
        offset, fmt, minimum, maximum = scalar_offsets[identity]
        value = int(edit.get("value"))
        if not minimum <= value <= maximum:
            raise ValueError(f"Field entrance value must be {minimum} to {maximum}")
        struct.pack_into("<" + fmt, raw, offset, value)
    reparsed = _parse_inf(raw)
    if reparsed["size"] != parsed["size"] or reparsed["variant"] != parsed["variant"]:
        raise ValueError("Field INF structure changed during save")
    return bytes(raw)


def _prepare_inf_edits(key: str, edits: list[dict]) -> tuple[Path, bytes]:
    row = _map_row(key)
    source = _inf_source_path(key, "current")
    if source is None:
        raise ValueError(f"Field map {key} has no INF records")
    raw = _edit_inf_bytes(source.read_bytes(), edits)
    destination = (paths.DIRECT_ROOT / DIRECT_SUBDIR / row["group"] / row["name"] /
                   f"{row['name']}.inf")
    return destination, raw


def _prepare_dialogue_edits(key: str, edits: list[dict]) -> tuple[Path, bytes, int]:
    row = _map_row(key)
    source = _dialogue_source_path(key, "current")
    if source is None:
        raise ValueError(f"Field map {key} has no dialogue MSD")
    raw, changed = field_dialogue.apply_edits(source.read_bytes(), [
        {"id": int(edit.get("line", -1)), "text": str(edit.get("text", ""))}
        for edit in edits
    ])
    destination = (paths.DIRECT_ROOT / DIRECT_SUBDIR / row["group"] / row["name"] /
                   f"{row['name']}.msd")
    return destination, raw, changed


def _prepare_script_documents(key: str, documents: list[dict]) -> tuple[Path, bytes, int]:
    row = _map_row(key)
    source, sym = _source_paths(key, "current")
    if source is None or sym is None:
        raise ValueError(f"Field map {key} has no JSM/SYM scripts")
    raw, changed = field_scripts.rebuild(source.read_bytes(), sym.read_bytes(), documents)
    destination = (paths.DIRECT_ROOT / DIRECT_SUBDIR / row["group"] / row["name"] /
                   f"{row['name']}.jsm")
    return destination, raw, changed


def _prepare_walkmesh_edits(key: str, edits: list[dict]) -> tuple[Path, bytes, int]:
    row = _map_row(key)
    source = _walkmesh_source_path(key, "current")
    if source is None:
        raise ValueError(f"Field map {key} has no walkmesh")
    raw, changed = field_walkmesh.apply_edits(source.read_bytes(), edits)
    destination = (paths.DIRECT_ROOT / DIRECT_SUBDIR / row["group"] / row["name"] /
                   f"{row['name']}.id")
    return destination, raw, changed


def _prepare_background_edits(key: str, edits: list[dict]) -> tuple[Path, bytes, int]:
    row = _map_row(key)
    map_source, mim_source = _background_source_paths(key, "current")
    if map_source is None or mim_source is None:
        raise ValueError(f"Field map {key} has no background")
    normalized = []
    allowed = {"tile", *field_background.editable_fields(
        field_background.read(map_source.read_bytes(), mim_source.read_bytes())["variant"])}
    for edit in edits:
        values = {name: value for name, value in edit.items()
                  if name not in {"type", "map"}}
        if set(values) - allowed:
            raise ValueError("Field background edit contains an unsupported tile field")
        normalized.append(values)
    raw, changed = field_background.apply_edits(
        map_source.read_bytes(), mim_source.read_bytes(), normalized)
    destination = (paths.DIRECT_ROOT / DIRECT_SUBDIR / row["group"] / row["name"] /
                   f"{row['name']}.map")
    return destination, raw, changed


def _prepare_encounter_edits(key: str, edits: list[dict]
                             ) -> list[tuple[Path, bytes, int]]:
    row = _map_row(key)
    mrt_source, rat_source = _encounter_source_paths(key, "current")
    if mrt_source is None or rat_source is None:
        raise ValueError(f"Field map {key} has no random encounter records")
    formation_edits = []
    rate_edits = []
    for edit in edits:
        kind = str(edit.get("kind", ""))
        if kind == "formation":
            formation_edits.append({
                "slot": int(edit.get("slot", -1)),
                "formation": int(edit.get("value", -1)),
            })
        elif kind == "rate":
            rate_edits.append(edit)
        else:
            raise ValueError("Unsupported field encounter edit kind")
    if len(rate_edits) > 1:
        raise ValueError("Duplicate field encounter rate edit")
    prepared = []
    directory = paths.DIRECT_ROOT / DIRECT_SUBDIR / row["group"] / row["name"]
    if formation_edits:
        raw, changed = field_encounters.apply_mrt_edits(
            mrt_source.read_bytes(), formation_edits)
        prepared.append((directory / f"{row['name']}.mrt", raw, changed))
    if rate_edits:
        raw, changed = field_encounters.apply_rat_edit(
            rat_source.read_bytes(), int(rate_edits[0].get("value", -1)))
        prepared.append((directory / f"{row['name']}.rat", raw, changed))
    return prepared


def save(edits: list[dict]) -> dict:
    by_map: dict[str, list[dict]] = {}
    for edit in edits:
        if edit.get("type", "card") not in {
                "card", "entrance", "dialogue", "script", "walkmesh", "background",
                "fieldEncounter"}:
            raise ValueError("Unsupported field edit type")
        by_map.setdefault(str(edit.get("map", "")), []).append(edit)
    written = 0
    inf_written = 0
    for key, map_edits in by_map.items():
        script_edits = [edit for edit in map_edits if edit.get("type", "card") == "card"]
        script_documents = [edit for edit in map_edits if edit.get("type") == "script"]
        entrance_edits = [edit for edit in map_edits if edit.get("type") == "entrance"]
        dialogue_edits = [edit for edit in map_edits if edit.get("type") == "dialogue"]
        walkmesh_edits = [edit for edit in map_edits if edit.get("type") == "walkmesh"]
        background_edits = [edit for edit in map_edits if edit.get("type") == "background"]
        encounter_edits = [edit for edit in map_edits
                           if edit.get("type") == "fieldEncounter"]
        prepared_inf = None
        prepared_dialogue = None
        if entrance_edits:
            prepared_inf = _prepare_inf_edits(key, entrance_edits)
        if dialogue_edits:
            prepared_dialogue = _prepare_dialogue_edits(key, dialogue_edits)
        prepared_walkmesh = None
        if walkmesh_edits:
            prepared_walkmesh = _prepare_walkmesh_edits(key, [{
                "triangle": int(edit.get("triangle", -1)),
                "vertex": int(edit.get("vertex", -1)),
                **{field: int(edit[field]) for field in ("x", "y", "z", "adjacent")
                   if field in edit},
            } for edit in walkmesh_edits])
        prepared_background = (_prepare_background_edits(key, background_edits)
                               if background_edits else None)
        prepared_encounters = (_prepare_encounter_edits(key, encounter_edits)
                               if encounter_edits else [])
        prepared_scripts = None
        if script_documents:
            prepared_scripts = _prepare_script_documents(key, [
                {"id": int(edit.get("method", -1)), "source": str(edit.get("source", ""))}
                for edit in script_documents
            ])
        if script_edits:
            row = _map_row(key)
            source, sym = _source_paths(key, "current")
            if source is None or sym is None:
                raise ValueError(f"Field map {key} has no JSM/SYM scripts")
            sym_raw = sym.read_bytes()
            original_players = _parse_card_players(source.read_bytes(), sym_raw)
            raw = bytearray(prepared_scripts[1] if prepared_scripts else source.read_bytes())
            players = _parse_card_players(raw, sym_raw)
            original_identity = [(value["entity"], value["script"])
                                 for value in original_players]
            rebuilt_identity = [(value["entity"], value["script"])
                                for value in players]
            if original_identity != rebuilt_identity:
                raise ValueError("General script edits changed the CARDGAME call order")
            seen = set()
            for edit in script_edits:
                player_id, param_id = int(edit.get("player", -1)), int(edit.get("param", -1))
                identity = (player_id, param_id)
                if identity in seen or not 0 <= player_id < len(players) or not 0 <= param_id < 7:
                    raise ValueError("Invalid or duplicate field card-player edit")
                seen.add(identity)
                param = players[player_id]["params"][param_id]
                if not param["editable"]:
                    raise ValueError("This field script expression is not a supported literal or variable push")
                value = int(edit.get("value"))
                if not 0 <= value <= 0xFFFFFF:
                    raise ValueError("Field script values must be 0 to 16777215")
                struct.pack_into("<I", raw, param["offset"], (param["opcode"] << 24) | value)
            _parse_card_players(raw, sym_raw)
            destination = (paths.DIRECT_ROOT / DIRECT_SUBDIR / row["group"] /
                           row["name"] / f"{row['name']}.jsm")
            prepared_scripts = (destination, bytes(raw),
                                (prepared_scripts[2] if prepared_scripts else 0) +
                                len(script_edits))
        if prepared_inf:
            _write_atomic(*prepared_inf)
            inf_written += len(entrance_edits)
        if prepared_dialogue:
            _write_atomic(prepared_dialogue[0], prepared_dialogue[1])
            written += prepared_dialogue[2]
        if prepared_scripts:
            _write_atomic(prepared_scripts[0], prepared_scripts[1])
            written += prepared_scripts[2]
        if prepared_walkmesh:
            _write_atomic(prepared_walkmesh[0], prepared_walkmesh[1])
            written += prepared_walkmesh[2]
        if prepared_background:
            _write_atomic(prepared_background[0], prepared_background[1])
            written += prepared_background[2]
        for destination, raw, changed in prepared_encounters:
            _write_atomic(destination, raw)
            written += changed
    return {"saved": written + inf_written, "maps": len(by_map)}
