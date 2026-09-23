"""Focused FF8 world-map encounter, region, and train-rail editor.

The proved layouts come from OpenVIII ``Core/World/wmset.cs`` and
``Core/World/rail.cs``, plus FF8 Ultimate Editor's Cid world-draw parser. The
wmset slice covers a 48-pointer header, four-byte encounter helpers in section
1, 768 region bytes in section 2, groups of eight little-endian scene IDs in
section 4, 64 field-to-world XYZ records in section 9, eight sky and ambient
colour records in section 33, and 128 fixed Draw Point position records in
section 34. Rail data uses fixed 2,048-byte track blocks
with a 12-byte header and signed XYZ keypoints. Unknown fields and all
unsupported world assets remain opaque and byte-identical on save.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile

from . import paths, runtime_layout, world_geometry, world_textures
from .fs_archive import FsArchive


WORLD_PREFIX = "world"
WORLD_ENTRY = "wmsetus.obj"
DIRECT_RELATIVE = Path("world/dat/wmsetus.obj")
BASELINE_RELATIVE = Path("world/wmsetus.obj")
RAIL_ENTRY = "rail.obj"
RAIL_DIRECT_RELATIVE = Path("world/dat/rail.obj")
RAIL_BASELINE_RELATIVE = Path("world/rail.obj")
REGION_COUNT = 32 * 24
SECTION_COUNT = 48
RAIL_BLOCK_SIZE = 2048
RAIL_HEADER_SIZE = 12
RAIL_POINT_SIZE = 16
RAIL_MAX_POINTS = (RAIL_BLOCK_SIZE - RAIL_HEADER_SIZE) // RAIL_POINT_SIZE
DRAW_SECTION = 34
DRAW_HEADER_SIZE = 0x2C
DRAW_RECORD_SIZE = 4
DRAW_POINT_COUNT = 128
FIELD_RETURN_SECTION = 8
FIELD_RETURN_RECORD_SIZE = 12
FIELD_RETURN_FOOTER_SIZE = 4
SKY_SECTION = 32
SKY_RECORD_SIZE = 52
SKY_COLOR_FIELDS = (
    ("shadows", 12),
    ("vehicles", 16),
    ("skyTop", 20),
    ("skyCenter", 24),
    ("skyBottom", 28),
)


def _archive_prefix() -> Path:
    return paths.GAME_ROOT / "Data" / "lang-en" / WORLD_PREFIX


def _fingerprint(prefix: Path) -> dict:
    return {
        suffix: {
            "size": prefix.with_suffix(suffix).stat().st_size,
            "mtimeNs": prefix.with_suffix(suffix).stat().st_mtime_ns,
        }
        for suffix in (".fs", ".fi", ".fl")
    }


def ensure_baseline() -> Path:
    """Extract only wmsetus.obj when its separate cache is absent or stale."""
    destination = paths.BASELINE_ROOT / BASELINE_RELATIVE
    metadata = destination.with_suffix(destination.suffix + ".source.json")
    prefix = _archive_prefix()
    current = _fingerprint(prefix)
    if destination.is_file() and metadata.is_file():
        try:
            if json.loads(metadata.read_text(encoding="utf-8")) == current:
                return destination
        except (OSError, ValueError, TypeError):
            pass
    archive = FsArchive(prefix)
    data = archive.extract(archive.find(WORLD_ENTRY))
    parse(data)  # Reject a corrupt or unexpected entry before caching it.
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    metadata.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return destination


def ensure_rail_baseline() -> Path:
    """Extract rail.obj into its own cache when it is absent or stale."""
    destination = paths.BASELINE_ROOT / RAIL_BASELINE_RELATIVE
    metadata = destination.with_suffix(destination.suffix + ".source.json")
    prefix = _archive_prefix()
    current = _fingerprint(prefix)
    if destination.is_file() and metadata.is_file():
        try:
            if json.loads(metadata.read_text(encoding="utf-8")) == current:
                return destination
        except (OSError, ValueError, TypeError):
            pass
    archive = FsArchive(prefix)
    data = archive.extract(archive.find(RAIL_ENTRY))
    parse_rail(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    metadata.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return destination


def source_path(dataset: str = "current") -> Path:
    baseline = ensure_baseline()
    if dataset == "vanilla":
        return baseline
    if dataset == "current":
        override = paths.DIRECT_ROOT / DIRECT_RELATIVE
        return override if override.is_file() else baseline
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        reference_root = paths.PROJECT_ROOT / "references" / reference_id
        candidates = (
            reference_root / "direct" / DIRECT_RELATIVE,
            reference_root / DIRECT_RELATIVE,
        )
        target = next((candidate for candidate in candidates if candidate.is_file()), None)
        if target is None:
            raise ValueError(f"wmsetus.obj is absent from reference {reference_id}")
        return target
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        candidates = (root / "direct" / DIRECT_RELATIVE, root / DIRECT_RELATIVE)
        return next((candidate for candidate in candidates if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def rail_source_path(dataset: str = "current") -> Path:
    baseline = ensure_rail_baseline()
    if dataset == "vanilla":
        return baseline
    if dataset == "current":
        override = paths.DIRECT_ROOT / RAIL_DIRECT_RELATIVE
        return override if override.is_file() else baseline
    if dataset.startswith("reference:"):
        reference_id = dataset.partition(":")[2]
        reference_root = paths.PROJECT_ROOT / "references" / reference_id
        candidates = (
            reference_root / "direct" / RAIL_DIRECT_RELATIVE,
            reference_root / RAIL_DIRECT_RELATIVE,
        )
        target = next((candidate for candidate in candidates if candidate.is_file()), None)
        # Older reference projects can contain wmsetus.obj without rail.obj.
        # An absent asset means that reference inherits vanilla for this slice;
        # it must not make the previously supported world dataset unreadable.
        return target if target is not None else baseline
    if dataset.startswith("mod:"):
        root = runtime_layout.root_for_mod(
            paths.PROJECT_ROOT, paths.MODS_ROOT, dataset.partition(":")[2])
        candidates = (root / "direct" / RAIL_DIRECT_RELATIVE,
                      root / RAIL_DIRECT_RELATIVE)
        return next((candidate for candidate in candidates if candidate.is_file()), baseline)
    raise ValueError(f"Unknown dataset: {dataset}")


def _pointers(data: bytes) -> tuple[int, ...]:
    if len(data) < SECTION_COUNT * 4:
        raise ValueError("wmsetus.obj is too small for its 48-section header")
    pointers = struct.unpack_from(f"<{SECTION_COUNT}I", data, 0)
    if pointers[0] < SECTION_COUNT * 4 or any(
        left > right for left, right in zip(pointers, pointers[1:])
    ) or pointers[-1] >= len(data):
        raise ValueError("wmsetus.obj has an invalid section pointer table")
    return pointers


def parse(data: bytes) -> dict:
    pointers = _pointers(data)
    section1, section2, section4 = pointers[0], pointers[1], pointers[3]
    if section2 + REGION_COUNT > pointers[2]:
        raise ValueError("wmsetus.obj section 2 does not contain 768 region bytes")

    helpers = []
    cursor = section1 + 4  # OpenVIII: first dword is the global-file end marker.
    while cursor + 4 <= pointers[1]:
        region_id, ground_id, encounter_group = struct.unpack_from("<BBH", data, cursor)
        if region_id == ground_id == encounter_group == 0:
            break
        helpers.append({"id": len(helpers), "regionId": region_id,
                        "groundId": ground_id, "encounterGroup": encounter_group})
        cursor += 4
    else:
        raise ValueError("wmsetus.obj section 1 has no encounter-helper terminator")

    regions = [
        {"id": index, "x": index % 32, "y": index // 32,
         "regionId": data[section2 + index]}
        for index in range(REGION_COUNT)
    ]

    groups = []
    cursor = section4
    while cursor + 4 <= pointers[4]:
        if data[cursor:cursor + 4] == b"\0\0\0\0":
            break
        if cursor + 16 > pointers[4]:
            raise ValueError("wmsetus.obj section 4 ends inside an encounter group")
        groups.append({"id": len(groups),
                       "encounters": list(struct.unpack_from("<8H", data, cursor))})
        cursor += 16
    else:
        raise ValueError("wmsetus.obj section 4 has no encounter-group terminator")

    if any(row["encounterGroup"] >= len(groups) for row in helpers):
        raise ValueError("wmsetus.obj contains an encounter helper with an invalid group")
    draw_start, draw_end = pointers[DRAW_SECTION], pointers[DRAW_SECTION + 1]
    expected_size = DRAW_HEADER_SIZE + DRAW_POINT_COUNT * DRAW_RECORD_SIZE
    if draw_end - draw_start != expected_size:
        raise ValueError(
            f"wmsetus.obj section 34 must contain {DRAW_POINT_COUNT} Draw Point records")
    records_start = draw_start + DRAW_HEADER_SIZE
    draw_points = []
    for index in range(DRAW_POINT_COUNT):
        x, y, sub_id, padding = struct.unpack_from(
            "<BBBB", data, records_start + index * DRAW_RECORD_SIZE)
        draw_points.append({"id": index, "drawId": 129 + index,
                            "name": f"Draw Point {129 + index}",
                            "x": x, "y": y, "subId": sub_id,
                            "padding": padding, "kind": "drawPoint"})
    return_start, return_end = pointers[FIELD_RETURN_SECTION], pointers[FIELD_RETURN_SECTION + 1]
    return_size = return_end - return_start
    if return_size < FIELD_RETURN_FOOTER_SIZE or (
            return_size - FIELD_RETURN_FOOTER_SIZE) % FIELD_RETURN_RECORD_SIZE:
        raise ValueError("wmsetus.obj field-to-world section has an invalid size")
    field_returns = []
    for index in range((return_size - FIELD_RETURN_FOOTER_SIZE) // FIELD_RETURN_RECORD_SIZE):
        offset = return_start + index * FIELD_RETURN_RECORD_SIZE
        x, z, y, unknown = struct.unpack_from("<iihh", data, offset)
        field_returns.append({"id": index, "name": f"Field return {index}",
                              "x": x, "y": y, "z": z, "unknown": unknown,
                              "kind": "fieldReturn"})
    sky_start, sky_end = pointers[SKY_SECTION], pointers[SKY_SECTION + 1]
    sky_pointers = []
    cursor = sky_start
    while cursor + 4 <= sky_end:
        relative = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        if relative == 0:
            break
        sky_pointers.append(relative)
    else:
        raise ValueError("wmsetus.obj sky section has no pointer terminator")
    if not sky_pointers or len(set(sky_pointers)) != len(sky_pointers):
        raise ValueError("wmsetus.obj sky section has an invalid pointer table")
    ordered_sky_pointers = sorted(sky_pointers)
    if any(right - left < SKY_RECORD_SIZE
           for left, right in zip(ordered_sky_pointers, ordered_sky_pointers[1:])):
        raise ValueError("wmsetus.obj sky section contains overlapping records")
    sky_colors = []
    for index, relative in enumerate(sky_pointers):
        offset = sky_start + relative
        if relative < cursor - sky_start or offset + SKY_RECORD_SIZE > sky_end:
            raise ValueError("wmsetus.obj sky section has an out-of-range record")
        # OpenVIII converts the stored X/Z/Y order into its world Vector3.
        x, z, y = struct.unpack_from("<iii", data, offset)
        row = {"id": index, "name": f"Sky record {index}", "x": x, "y": y,
               "z": z, "kind": "skyColor", "recordOffset": relative}
        for key, color_offset in SKY_COLOR_FIELDS:
            row[key] = list(struct.unpack_from("<BBB", data, offset + color_offset))
        sky_colors.append(row)
    return {"helpers": helpers, "regions": regions, "groups": groups,
            "drawPoints": draw_points, "fieldReturns": field_returns,
            "skyColors": sky_colors,
            "width": 32, "height": 24}


def parse_rail(data: bytes) -> dict:
    """Parse only the rail fields proved by OpenVIII's fixed-block reader."""
    if not data or len(data) % RAIL_BLOCK_SIZE:
        raise ValueError("rail.obj is not made of complete 2,048-byte track blocks")
    tracks = []
    for track_id, offset in enumerate(range(0, len(data), RAIL_BLOCK_SIZE)):
        point_count, _unknown8, _unknown16, stop1, stop2 = struct.unpack_from(
            "<BBHII", data, offset)
        if point_count > RAIL_MAX_POINTS:
            raise ValueError(f"rail.obj track {track_id} has too many keypoints")
        if point_count == 0:
            if stop1 or stop2:
                raise ValueError(f"rail.obj empty track {track_id} has invalid stops")
        elif stop1 >= point_count or stop2 >= point_count:
            raise ValueError(f"rail.obj track {track_id} has an invalid stop index")
        points = []
        for point_id in range(point_count):
            point_offset = offset + RAIL_HEADER_SIZE + point_id * RAIL_POINT_SIZE
            x, y, z, _unknown = struct.unpack_from("<iiii", data, point_offset)
            points.append({"id": point_id, "x": x, "y": y, "z": z})
        tracks.append({"id": track_id, "kind": "railTrack",
                       "pointCount": point_count, "trainStop1": stop1,
                       "trainStop2": stop2, "points": points})
    return {"tracks": tracks}


def rows(dataset: str = "current") -> dict:
    parsed = parse(source_path(dataset).read_bytes())
    rail = parse_rail(rail_source_path(dataset).read_bytes())
    texture_data = world_textures.rows(dataset)
    geometry_data = world_geometry.rows(dataset)
    flattened = [
        *({**row, "kind": "helper"} for row in parsed["helpers"]),
        *({**row, "kind": "region"} for row in parsed["regions"]),
        *({**row, "kind": "group"} for row in parsed["groups"]),
        *parsed["drawPoints"],
        *parsed["fieldReturns"],
        *parsed["skyColors"],
        *geometry_data["segments"],
        *rail["tracks"],
        *texture_data["textures"],
    ]
    return {**parsed, **rail, "textures": texture_data["textures"],
            "segments": geometry_data["segments"], "rows": flattened,
            "source": str(source_path(dataset)),
            "railSource": str(rail_source_path(dataset)),
            "textureSource": texture_data["source"],
            "geometrySource": geometry_data["source"],
            "sha256": hashlib.sha256(source_path(dataset).read_bytes()).hexdigest(),
            "railSha256": hashlib.sha256(rail_source_path(dataset).read_bytes()).hexdigest(),
            "textureSha256": texture_data["sha256"],
            "geometrySha256": geometry_data["sha256"]}


def _bounded(value, minimum: int, maximum: int, label: str) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be {minimum} to {maximum}")
    return value


def apply_rail_edits(data: bytes | bytearray, edits: list[dict]) -> bytearray:
    """Apply track mutations without rebuilding blocks or touching unknown bytes."""
    raw = bytearray(data)
    parsed = parse_rail(raw)
    for edit in edits:
        track_id = _bounded(edit.get("id"), 0, len(parsed["tracks"]) - 1, "Track ID")
        track = parsed["tracks"][track_id]
        count = track["pointCount"]
        if count == 0:
            raise ValueError("Empty rail tracks cannot have editable stops or keypoints")
        stop1 = _bounded(edit.get("trainStop1"), 0, count - 1, "Train stop 1")
        stop2 = _bounded(edit.get("trainStop2"), 0, count - 1, "Train stop 2")
        points = edit.get("points")
        if not isinstance(points, list) or len(points) != count:
            raise ValueError(f"Rail track {track_id} must contain {count} keypoints")
        offset = track_id * RAIL_BLOCK_SIZE
        struct.pack_into("<II", raw, offset + 4, stop1, stop2)
        for point_id, point in enumerate(points):
            if not isinstance(point, dict) or int(point.get("id", -1)) != point_id:
                raise ValueError(f"Rail track {track_id} keypoints must stay in order")
            point_offset = offset + RAIL_HEADER_SIZE + point_id * RAIL_POINT_SIZE
            for component_offset, key, label in (
                (0, "x", "Rail X"), (4, "y", "Rail Y"), (8, "z", "Rail Z")):
                value = _bounded(point.get(key), -(2 ** 31), 2 ** 31 - 1, label)
                struct.pack_into("<i", raw, point_offset + component_offset, value)
    parse_rail(raw)
    return raw


def apply_draw_point_edits(data: bytes | bytearray, edits: list[dict]) -> bytearray:
    """Edit only the three proved bytes in fixed section-34 Draw Point records."""
    raw = bytearray(data)
    parsed = parse(raw)
    pointers = _pointers(raw)
    seen = set()
    for edit in edits:
        index = _bounded(edit.get("id"), 0, DRAW_POINT_COUNT - 1, "Draw Point ID")
        if index in seen:
            raise ValueError(f"Duplicate world Draw Point edit: {index}")
        seen.add(index)
        x = _bounded(edit.get("x"), 0, 255, "Draw Point X")
        y = _bounded(edit.get("y"), 0, 255, "Draw Point Y")
        sub_id = _bounded(edit.get("subId"), 0, 255, "Draw Point sub-ID")
        record_offset = (pointers[DRAW_SECTION] + DRAW_HEADER_SIZE
                         + index * DRAW_RECORD_SIZE)
        struct.pack_into("<BBB", raw, record_offset, x, y, sub_id)
    parse(raw)
    return raw


def apply_field_return_edits(data: bytes | bytearray, edits: list[dict]) -> bytearray:
    """Edit proved XYZ values while preserving each record's unknown word."""
    raw = bytearray(data)
    parsed = parse(raw)
    pointers = _pointers(raw)
    seen = set()
    for edit in edits:
        index = _bounded(edit.get("id"), 0, len(parsed["fieldReturns"]) - 1,
                         "Field-return ID")
        if index in seen:
            raise ValueError(f"Duplicate field-to-world edit: {index}")
        seen.add(index)
        x = _bounded(edit.get("x"), -(2 ** 31), 2 ** 31 - 1, "Field-return X")
        y = _bounded(edit.get("y"), -32768, 32767, "Field-return Y")
        z = _bounded(edit.get("z"), -(2 ** 31), 2 ** 31 - 1, "Field-return Z")
        offset = pointers[FIELD_RETURN_SECTION] + index * FIELD_RETURN_RECORD_SIZE
        struct.pack_into("<iih", raw, offset, x, z, y)
    parse(raw)
    return raw


def apply_sky_color_edits(data: bytes | bytearray, edits: list[dict]) -> bytearray:
    """Edit proved section-33 positions and RGB triples; preserve unknown bytes."""
    raw = bytearray(data)
    parsed = parse(raw)
    pointers = _pointers(raw)
    seen = set()
    for edit in edits:
        index = _bounded(edit.get("id"), 0, len(parsed["skyColors"]) - 1,
                         "Sky-record ID")
        if index in seen:
            raise ValueError(f"Duplicate sky-record edit: {index}")
        seen.add(index)
        row = parsed["skyColors"][index]
        offset = pointers[SKY_SECTION] + int(row["recordOffset"])
        coordinates = [
            _bounded(edit.get(key), -(2 ** 31), 2 ** 31 - 1,
                     f"Sky-record {key.upper()}")
            for key in ("x", "y", "z")
        ]
        struct.pack_into("<iii", raw, offset, coordinates[0], coordinates[2],
                         coordinates[1])
        for key, color_offset in SKY_COLOR_FIELDS:
            color = edit.get(key)
            if not isinstance(color, list) or len(color) != 3:
                raise ValueError(f"Sky-record {key} must contain three RGB bytes")
            rgb = [_bounded(value, 0, 255, f"Sky-record {key} channel")
                   for value in color]
            struct.pack_into("<BBB", raw, offset + color_offset, *rgb)
    parse(raw)
    return raw


def _atomic_write(destination: Path, raw: bytes | bytearray) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(destination, destination.with_name(f"{destination.name}.{stamp}.bak"))
    handle, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp",
                                         dir=destination.parent)
    try:
        with open(handle, "wb", closefd=True) as stream:
            stream.write(raw)
        Path(temp_name).replace(destination)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def save(edits: list[dict]) -> dict:
    source = source_path("current")
    raw = bytearray(source.read_bytes())
    parsed = parse(raw)
    pointers = _pointers(raw)
    draw_edits = [edit for edit in edits if str(edit.get("kind", "")) == "drawPoint"]
    if draw_edits:
        raw = apply_draw_point_edits(raw, draw_edits)
    field_return_edits = [edit for edit in edits
                          if str(edit.get("kind", "")) == "fieldReturn"]
    if field_return_edits:
        raw = apply_field_return_edits(raw, field_return_edits)
    sky_color_edits = [edit for edit in edits
                       if str(edit.get("kind", "")) == "skyColor"]
    if sky_color_edits:
        raw = apply_sky_color_edits(raw, sky_color_edits)
    changed = len(draw_edits) + len(field_return_edits) + len(sky_color_edits)
    rail_edits = [edit for edit in edits if str(edit.get("kind", "")) == "railTrack"]
    texture_edits = [edit for edit in edits if str(edit.get("kind", "")) == "worldTexture"]
    geometry_edits = [edit for edit in edits if str(edit.get("kind", "")) == "worldSegment"]
    wmset_edits = [edit for edit in edits if str(edit.get("kind", "")) not in (
        "drawPoint", "fieldReturn", "skyColor", "railTrack", "worldTexture",
        "worldSegment")]
    for edit in wmset_edits:
        kind = str(edit.get("kind", ""))
        index = _bounded(edit.get("id"), 0, 100000, "Record ID")
        if kind == "region":
            if index >= len(parsed["regions"]):
                raise ValueError("Unknown world region cell")
            value = _bounded(edit.get("regionId"), 0, 255, "Region ID")
            raw[pointers[1] + index] = value
        elif kind == "helper":
            if index >= len(parsed["helpers"]):
                raise ValueError("Unknown encounter helper")
            region_id = _bounded(edit.get("regionId"), 0, 255, "Region ID")
            ground_id = _bounded(edit.get("groundId"), 0, 255, "Ground ID")
            group = _bounded(edit.get("encounterGroup"), 0, len(parsed["groups"]) - 1,
                             "Encounter group")
            struct.pack_into("<BBH", raw, pointers[0] + 4 + index * 4,
                             region_id, ground_id, group)
        elif kind == "group":
            if index >= len(parsed["groups"]):
                raise ValueError("Unknown encounter group")
            encounters = edit.get("encounters")
            if not isinstance(encounters, list) or len(encounters) != 8:
                raise ValueError("Encounter groups must contain eight scene IDs")
            values = [_bounded(value, 0, 1023, "Encounter ID") for value in encounters]
            struct.pack_into("<8H", raw, pointers[3] + index * 16, *values)
        else:
            raise ValueError(f"Unknown world-map record kind: {kind}")
        changed += 1

    # Validate every complete result before replacing either project override.
    parse(raw)
    rail_raw = (apply_rail_edits(rail_source_path("current").read_bytes(), rail_edits)
                if rail_edits else None)
    texture_raw = (world_textures.apply_edits(
        world_textures.source_path("current").read_bytes(), texture_edits)
        if texture_edits else None)
    geometry_raw = (world_geometry.apply_edits(
        world_geometry.source_path("current").read_bytes(), geometry_edits)
        if geometry_edits else None)
    destinations = []
    if wmset_edits or draw_edits or field_return_edits or sky_color_edits:
        destination = paths.DIRECT_ROOT / DIRECT_RELATIVE
        _atomic_write(destination, raw)
        destinations.append(str(destination))
    if rail_edits:
        rail_destination = paths.DIRECT_ROOT / RAIL_DIRECT_RELATIVE
        _atomic_write(rail_destination, rail_raw)
        destinations.append(str(rail_destination))
        changed += len(rail_edits)
    if texture_edits:
        texture_destination = paths.DIRECT_ROOT / world_textures.DIRECT_RELATIVE
        _atomic_write(texture_destination, texture_raw)
        destinations.append(str(texture_destination))
        changed += len(texture_edits)
    if geometry_edits:
        geometry_destination = paths.DIRECT_ROOT / world_geometry.DIRECT_RELATIVE
        _atomic_write(geometry_destination, geometry_raw)
        destinations.append(str(geometry_destination))
        changed += len(geometry_edits)
    return {"saved": changed, "file": destinations[0] if destinations else "",
            "files": destinations}
