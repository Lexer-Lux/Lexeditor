"""Local JSON and UI service for the Red Dead Redemption Lexeditor plugin."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import math
import os
import re
import struct
import subprocess
import tempfile
import uuid
import webbrowser
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlparse

from . import mission_rewards, paths


PLUGIN_ROOT = Path(__file__).resolve().parent
LEXEDITOR_ROOT = PLUGIN_ROOT.parents[1]
PROJECT = paths.PROJECT_ROOT
MOD_ROOT = paths.MOD_ROOT
GAME_ROOT = paths.GAME_ROOT
EXTRACT_ROOT = paths.EXTRACT_ROOT
PREPARED_ROOT = EXTRACT_ROOT / "tune_d11generic"
OVERRIDE_ROOT = MOD_ROOT / "tune_d11generic"
CONTENT_PREPARED_ROOT = EXTRACT_ROOT / "content"
CONTENT_OVERRIDE_ROOT = MOD_ROOT / "content"
GRINGO_PACKED_ROOT = EXTRACT_ROOT / "gringores"
GRINGO_UNPACKED_ROOT = EXTRACT_ROOT / "gringores-unpacked"
GRINGO_OVERRIDE_ROOT = MOD_ROOT / "gringores"
SETTINGS_FILE = paths.SETTINGS_FILE
LOOT_FILE = Path(
    os.environ.get("LEXEDITOR_RDR_LOOT", PROJECT / "LexerRDR.loot.json")
).expanduser().resolve()
DATA_MAP_FILE = Path(
    os.environ.get("LEXEDITOR_RDR_DATA_MAP", PLUGIN_ROOT / "data_map.generated.json")
).expanduser().resolve()
INVENTORY_SOURCES = {
    "base": {
        "label": "Base game",
        "relative": PurePosixPath("content/init/inventory/inventory.xml"),
    },
    "dlc": {
        "label": "Undead Nightmare DLC",
        "relative": PurePosixPath("content/init/inventory/dlc_inventory.xml"),
    },
}
PORT = int(os.environ.get("LEXEDITOR_PORT", "8767"))
HOSTED = os.environ.get("LEXEDITOR_PLUGIN_HOSTED", "0") == "1"
WINDOW_HOST = os.environ.get("LEXEDITOR_WINDOW_HOST", "")
MAX_TEXT_BYTES = 8 * 1024 * 1024
TEXT_EXTENSIONS = {
    ".arm", ".cfg", ".charclothmanager", ".clm", ".colors", ".csv",
    ".dat", ".env", ".envclothmanager", ".expl", ".film", ".flare",
    ".fx", ".fxm", ".hud", ".list", ".mtl", ".pop", ".ppp",
    ".refgroup", ".rmptx", ".spm", ".streaming", ".textune", ".tod",
    ".todlight", ".tr", ".traffic", ".trainmanager", ".tune", ".tuning",
    ".vehboat", ".vehdraft", ".vehgyro", ".vehinput", ".vehmodel",
    ".vehpushcart", ".vehsim", ".vehstuck", ".weap", ".xml", ".txt",
}
ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")
INI_SETTING = re.compile(r"^(?P<prefix>\s*[^#;\s][^=]*?\s*=\s*)(?P<value>.*)$")
REDHOOK_URL = "https://www.nexusmods.com/reddeadredemption/mods/192"
REDHOOK_FILES = ("RedHook.dll", "winmm.dll", "RedHook.ini")
REDHOOK_SKIP_INTRO = re.compile(
    r"^(?P<prefix>\s*SkipIntroLogos\s*=\s*)(?P<value>[^;#\r\n]*?)"
    r"(?P<suffix>\s*(?:[;#].*)?)$",
    re.IGNORECASE | re.MULTILINE,
)
SHOP_INVENTORY_HASH = 0x1C51E604
SHOP_CONTAINER_TYPE = 0xD6F7F3F1
SHOP_ITEM_TYPE = 0xB16C14A8
STRING_ATTRIBUTE_TYPE = 0x3EED2FB8
FLOAT_ATTRIBUTE_TYPE = 0x178DF99A
VARIABLE_INT_ATTRIBUTE_TYPE = 0x7EB41668
SHOP_ATTRIBUTE_HASHES = {
    0xDE02D359: "ITEM_/AMMO_/WE_Enum",
    0x65E7F789: "PriceModifier",
    0x7EBD2697: "QuantityPerPurchase",
    0x7992CBA6: "TotalAvailableQuantity",
}
ITEM_SELECT_FIELDS = {"mp_EquipStringId", "mp_UnequipStringId"}
ITEM_NUMBER_CONTROLS = {
    "HUDReticleIndex": {"minimum": -1, "maximum": 255, "step": 1},
    "MaxItemCount": {"minimum": -1, "maximum": 100000, "step": 1},
    "SpawnTimeOut": {"minimum": 0, "maximum": 86400, "step": 0.1},
}
SETTING_CONTROLS = {
    ("weaponradial", "timescale"): {"control": "number", "minimum": 0.01, "maximum": 1, "step": 0.01},
    ("persistenthud", "right"): {"control": "number", "minimum": 0, "maximum": 1, "step": 0.001},
    ("persistenthud", "moneyy"): {"control": "number", "minimum": 0, "maximum": 1, "step": 0.001},
    ("persistenthud", "ammoy"): {"control": "number", "minimum": 0, "maximum": 1, "step": 0.001},
    ("persistenthud", "scale"): {"control": "number", "minimum": 0.01, "maximum": 0.2, "step": 0.005},
    ("developmentcamera", "movespeed"): {"control": "number", "minimum": 0.1, "maximum": 100, "step": 0.1},
    ("developmentcamera", "boostmultiplier"): {"control": "number", "minimum": 1, "maximum": 20, "step": 0.1},
    ("developmentcamera", "rotationspeed"): {"control": "number", "minimum": 1, "maximum": 360, "step": 1},
}


def atomic_bytes(target: Path, payload: bytes) -> None:
    """Replace one project file after its complete payload reaches disk."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_file(target: Path) -> Path | None:
    if not target.is_file():
        return None
    backup = target.with_name(target.name + ".lexeditor.bak")
    atomic_bytes(backup, target.read_bytes())
    return backup


def safe_relative(value: str) -> PurePosixPath:
    normalized = value.replace("\\", "/").strip("/")
    relative = PurePosixPath(normalized)
    if (not normalized or relative.is_absolute() or
            any(part in {"", ".", ".."} for part in relative.parts)):
        raise ValueError("Invalid prepared file path")
    return relative


def under(root: Path, relative: PurePosixPath) -> Path:
    resolved_root = root.resolve()
    target = (resolved_root / Path(*relative.parts)).resolve()
    if target != resolved_root and resolved_root not in target.parents:
        raise ValueError("File path escapes the RDR workspace")
    return target


def prepared_file(value: str) -> tuple[PurePosixPath, Path]:
    relative = safe_relative(value)
    target = under(PREPARED_ROOT, relative)
    if not target.is_file():
        raise FileNotFoundError(f"Prepared RDR file not found: {relative.as_posix()}")
    return relative, target


def override_file(relative: PurePosixPath) -> Path:
    return under(OVERRIDE_ROOT, relative)


def is_editable(path: Path) -> bool:
    return path.suffix.casefold() in TEXT_EXTENSIONS and path.stat().st_size <= MAX_TEXT_BYTES


def decode_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if len(raw) > MAX_TEXT_BYTES:
        raise ValueError("This file is too large for the source editor")
    if b"\x00" in raw[:4096]:
        raise ValueError("This file is binary and cannot be edited as text")
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    raise ValueError("Lexeditor could not decode this file as text")


def files_payload() -> dict:
    rows = []
    if PREPARED_ROOT.is_dir():
        for source in PREPARED_ROOT.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(PREPARED_ROOT)
            relative_text = relative.as_posix()
            project = override_file(PurePosixPath(relative_text))
            parts = relative.parts
            rows.append({
                "path": relative_text,
                "name": source.name,
                "category": parts[1] if len(parts) > 2 and parts[0].casefold() == "tune" else parts[0],
                "extension": source.suffix.casefold() or "(none)",
                "size": source.stat().st_size,
                "editable": is_editable(source),
                "project": project.is_file(),
            })
    rows.sort(key=lambda row: row["path"].casefold())
    return {
        "rows": rows,
        "counts": {
            "all": len(rows),
            "editable": sum(row["editable"] for row in rows),
            "project": sum(row["project"] for row in rows),
        },
        "preparedRoot": str(PREPARED_ROOT),
        "overrideRoot": str(OVERRIDE_ROOT),
    }


def read_file(value: str) -> dict:
    relative, vanilla = prepared_file(value)
    project = override_file(relative)
    active = project if project.is_file() else vanilla
    editable = is_editable(vanilla)
    if not editable:
        return {
            "path": relative.as_posix(),
            "name": vanilla.name,
            "editable": False,
            "source": "project" if project.is_file() else "vanilla",
            "sourcePath": str(vanilla),
            "projectPath": str(project),
            "text": "",
            "encoding": "",
            "reason": "This file needs a format-specific editor.",
        }
    text, encoding = decode_text(active)
    return {
        "path": relative.as_posix(),
        "name": vanilla.name,
        "editable": True,
        "source": "project" if project.is_file() else "vanilla",
        "sourcePath": str(vanilla),
        "projectPath": str(project),
        "text": text,
        "encoding": encoding,
        "reason": "",
    }


def save_file(value: str, text: str, encoding: str) -> dict:
    relative, vanilla = prepared_file(value)
    if not is_editable(vanilla):
        raise ValueError("This prepared file is not editable as text")
    if encoding not in ENCODINGS:
        raise ValueError("Unsupported text encoding")
    encoded = text.encode(encoding)
    if len(encoded) > MAX_TEXT_BYTES:
        raise ValueError("Edited text is too large")
    if vanilla.suffix.casefold() == ".xml":
        try:
            ET.fromstring(text)
        except ET.ParseError as error:
            raise ValueError(f"XML is not valid: {error}") from error

    target = override_file(relative)
    backup = backup_file(target)
    atomic_bytes(target, encoded)
    return {
        "saved": 1,
        "path": relative.as_posix(),
        "projectPath": str(target),
        "backup": str(backup) if backup else "",
        "bytes": len(encoded),
    }


def _inventory_paths(source_id: str, vanilla_only: bool = False) -> tuple[dict, Path, Path, Path]:
    source = INVENTORY_SOURCES.get(source_id)
    if source is None:
        raise ValueError(f"Unknown inventory source: {source_id}")
    relative = source["relative"]
    vanilla = under(CONTENT_PREPARED_ROOT, relative)
    project = under(CONTENT_OVERRIDE_ROOT, relative)
    if not vanilla.is_file():
        raise FileNotFoundError(f"Prepared RDR inventory file not found: {vanilla}")
    active = project if project.is_file() and not vanilla_only else vanilla
    return source, vanilla, project, active


def _xml_tree(path: Path) -> ET.ElementTree:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser)


def _item_name(item: ET.Element) -> str:
    node = item.find("Name")
    return (node.text or "").strip() if node is not None else ""


def _scalar_field(node: ET.Element) -> dict | None:
    if list(node) or not isinstance(node.tag, str):
        return None
    if set(node.attrib) == {"value"}:
        value = node.get("value", "")
        storage = "value"
    elif set(node.attrib).issubset({"content"}):
        value = node.text or ""
        storage = "text"
    elif not node.attrib:
        value = node.text or ""
        storage = "text"
    else:
        return None
    lowered = value.casefold()
    if lowered in {"true", "false"}:
        kind = "bool"
    else:
        try:
            float(value)
            kind = "number"
        except ValueError:
            kind = "text"
    return {"field": node.tag, "value": value, "storage": storage, "kind": kind}


def items_payload(vanilla_only: bool = False) -> dict:
    rows = []
    source_rows = []
    for source_id, definition in INVENTORY_SOURCES.items():
        try:
            source, vanilla, project, active = _inventory_paths(source_id, vanilla_only)
        except FileNotFoundError:
            source_rows.append({
                "id": source_id,
                "label": definition["label"],
                "available": False,
            })
            continue
        tree = _xml_tree(active)
        records = tree.findall("./Types/Item")
        source_rows.append({
            "id": source_id,
            "label": source["label"],
            "available": True,
            "count": len(records),
            "sourcePath": str(vanilla),
            "projectPath": str(project),
            "project": project.is_file() and not vanilla_only,
        })
        for index, item in enumerate(records):
            fields = [field for child in list(item)
                      if (field := _scalar_field(child)) is not None]
            by_name = {field["field"]: field["value"] for field in fields}
            name = by_name.get("Name", "")
            rows.append({
                "id": f"{source_id}:{index}",
                "source": source_id,
                "sourceLabel": source["label"],
                "index": index,
                "name": name,
                "friendlyName": by_name.get("FriendlyName", ""),
                "type": item.get("type", ""),
                "icon": by_name.get("mp_IconName", ""),
                "project": project.is_file() and not vanilla_only,
                "fields": fields,
                "sourcePath": str(vanilla),
                "projectPath": str(project),
            })
    choices = {}
    for field_name in ITEM_SELECT_FIELDS:
        choices[field_name] = sorted({
            field["value"]
            for row in rows for field in row["fields"]
            if field["field"] == field_name
        }, key=str.casefold)
    for row in rows:
        for field in row["fields"]:
            if field["kind"] == "bool":
                field["control"] = "checkbox"
            elif field["field"] in choices:
                field["control"] = "select"
                field["options"] = choices[field["field"]]
            elif field["kind"] == "number":
                field["control"] = "number"
                limits = ITEM_NUMBER_CONTROLS.get(field["field"], {})
                field.update(limits)
                field.setdefault(
                    "step", 1 if re.fullmatch(r"[+-]?\d+", field["value"].strip()) else 0.01)
            else:
                field["control"] = "text"
    return {
        "rows": rows,
        "sources": source_rows,
        "counts": {
            "all": len(rows),
            "base": sum(row["source"] == "base" for row in rows),
            "dlc": sum(row["source"] == "dlc" for row in rows),
            "project": sum(row["project"] for row in rows),
        },
    }


def _edit_list(edits: list[dict]) -> list[dict]:
    if not isinstance(edits, list) or any(not isinstance(edit, dict) for edit in edits):
        raise ValueError("Edits must be a list of objects")
    return edits


def _number(value, label: str, minimum=None, maximum=None, *, integer=False) -> float:
    """Validate before converting: bool and empty text are not numeric edits."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{label} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{label} must be a number") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    if integer and not number.is_integer():
        raise ValueError(f"{label} must be an integer")
    if minimum is not None and number < minimum or maximum is not None and number > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _validate_scalar(original: str, kind: str, value: str, field: str) -> str:
    if "\x00" in value or len(value) > 4096:
        raise ValueError(f"{field} contains an invalid value")
    if kind == "bool":
        lowered = value.strip().casefold()
        if lowered not in {"true", "false"}:
            raise ValueError(f"{field} must be true or false")
        return lowered
    if kind == "number":
        limits = ITEM_NUMBER_CONTROLS.get(field, {})
        integer = limits.get("step") == 1 if limits else bool(re.fullmatch(r"[+-]?\d+", original.strip()))
        _number(value, field, limits.get("minimum"), limits.get("maximum"), integer=integer)
    return value


def save_item(source_id: str, index: int, expected_name: str, edits: list[dict]) -> dict:
    _integer(index, "Inventory item index", 0, 2147483647)
    _source, vanilla, project, active = _inventory_paths(source_id)
    tree = _xml_tree(active)
    records = tree.findall("./Types/Item")
    if index < 0 or index >= len(records):
        raise ValueError("Inventory item index is out of range")
    item = records[index]
    if _item_name(item) != expected_name:
        raise ValueError("The inventory source changed; reload the item before saving")
    direct = {child.tag: child for child in list(item) if isinstance(child.tag, str)}
    wanted = {}
    for edit in _edit_list(edits):
        field = str(edit.get("field", ""))
        if not field or field in wanted:
            raise ValueError("Each item field must be named once")
        node = direct.get(field)
        scalar = _scalar_field(node) if node is not None else None
        if scalar is None:
            raise ValueError(f"Unsupported or missing item field: {field}")
        value = _validate_scalar(scalar["value"], scalar["kind"], str(edit.get("value", "")), field)
        if field in ITEM_SELECT_FIELDS:
            # Observed enum values from the prepared source and current project.
            options = {candidate["value"] for dataset in (True, False)
                       for row in items_payload(dataset)["rows"] for candidate in row["fields"]
                       if candidate["field"] == field}
            if value not in options:
                raise ValueError(f"Unsupported {field} choice: {value}")
        if field == "Name" and not value.strip():
            raise ValueError("Name cannot be empty")
        wanted[field] = (node, scalar, value)
    changed = 0
    for node, scalar, value in wanted.values():
        if value == scalar["value"]:
            continue
        if scalar["storage"] == "value":
            node.set("value", value)
        else:
            node.text = value
        changed += 1
    if not changed:
        return {"saved": 0, "projectPath": str(project), "backup": ""}
    payload = ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)
    # Validate the exact payload before it can replace a project file.
    ET.fromstring(payload)
    backup = backup_file(project)
    atomic_bytes(project, payload)
    verify = _xml_tree(project).findall("./Types/Item")[index]
    for field, (_node, _scalar, value) in wanted.items():
        actual = _scalar_field(next(child for child in list(verify) if child.tag == field))
        if actual is None or actual["value"] != value:
            raise RuntimeError(f"Saved inventory field did not read back: {field}")
    return {
        "saved": changed,
        "source": source_id,
        "index": index,
        "projectPath": str(project),
        "backup": str(backup) if backup else "",
        "sourceUnchanged": sha256_file(vanilla),
    }


def _u32(data: bytes | bytearray, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError("Shop dictionary contains an out-of-range value")
    return struct.unpack_from("<I", data, offset)[0]


def _resource_offset(value: int, aligned_object: bool = False) -> int:
    if value >> 28 != 5:
        raise ValueError("Shop dictionary contains an invalid virtual pointer")
    offset = value & 0x0FFFFFFF
    return offset & ~3 if aligned_object else offset


def _array_values(data: bytes | bytearray, header: int,
                  aligned_objects: bool = False) -> list[int]:
    base = _resource_offset(_u32(data, header))
    count = _u32(data, header + 4) & 0xFFFF
    if count > 32768 or base + count * 4 > len(data):
        raise ValueError("Shop dictionary contains an invalid array")
    values = [_u32(data, base + index * 4) for index in range(count)]
    if aligned_objects:
        return [_resource_offset(value, True) for value in values]
    return values


def _resource_string(data: bytes | bytearray, value: int) -> str:
    offset = _resource_offset(value)
    if offset >= len(data):
        raise ValueError("Shop dictionary contains an invalid string pointer")
    end = bytes(data).find(b"\x00", offset, min(len(data), offset + 4096))
    if end < 0:
        raise ValueError("Shop dictionary contains an unterminated string")
    return bytes(data[offset:end]).decode("ascii")


def _shop_records(data: bytes | bytearray, relative: PurePosixPath,
                  project: bool) -> list[dict]:
    root_hashes = _array_values(data, 16)
    roots = _array_values(data, 24, aligned_objects=True)
    if len(root_hashes) != len(roots):
        raise ValueError("Shop dictionary root tables do not match")
    records = []
    shop_roots = []
    for root_hash, root in zip(root_hashes, roots):
        script = _resource_string(data, _u32(data, root + 32))
        if not script.casefold().endswith("shopkeeper_brain"):
            continue
        for component in _array_values(data, root + 40, aligned_objects=True):
            if (_u32(data, component) == SHOP_CONTAINER_TYPE
                    and _u32(data, component + 8) == SHOP_INVENTORY_HASH):
                shop_roots.append((root_hash, component))
    for shop_number, (root_hash, inventory) in enumerate(shop_roots, 1):
        children = _array_values(data, inventory + 16, aligned_objects=True)
        shop_label = relative.stem.replace("_", " ").title()
        if len(shop_roots) > 1:
            shop_label += f" · Shop {shop_number}"
        for item_index, child in enumerate(children):
            if _u32(data, child) != SHOP_ITEM_TYPE:
                continue
            attributes = {}
            offsets = {}
            for attribute in _array_values(data, child + 16, aligned_objects=True):
                attribute_type = _u32(data, attribute)
                attribute_name = SHOP_ATTRIBUTE_HASHES.get(_u32(data, attribute + 4))
                if attribute_name is None:
                    continue
                if attribute_name == "ITEM_/AMMO_/WE_Enum":
                    if attribute_type != STRING_ATTRIBUTE_TYPE:
                        raise ValueError("Shop item identifier has the wrong attribute type")
                    attributes[attribute_name] = _resource_string(
                        data, _u32(data, attribute + 8))
                elif attribute_name == "PriceModifier":
                    if attribute_type != FLOAT_ATTRIBUTE_TYPE:
                        raise ValueError("Shop price modifier has the wrong attribute type")
                    attributes[attribute_name] = struct.unpack_from(
                        "<f", data, attribute + 8)[0]
                    offsets[attribute_name] = attribute + 8
                else:
                    if attribute_type != VARIABLE_INT_ATTRIBUTE_TYPE:
                        raise ValueError(f"{attribute_name} has the wrong attribute type")
                    attributes[attribute_name] = struct.unpack_from(
                        "<i", data, attribute + 12)[0]
                    offsets[attribute_name] = attribute + 12
            item_name = attributes.get("ITEM_/AMMO_/WE_Enum", "")
            required = {
                "PriceModifier", "QuantityPerPurchase", "TotalAvailableQuantity",
            }
            if not item_name or not required.issubset(attributes):
                continue
            category = item_name.split("_", 1)[0]
            root_identity = f"{root_hash:08X}"
            records.append({
                "id": f"{relative.as_posix()}|{root_identity}|{item_index}",
                "source": relative.as_posix(),
                "rootHash": root_identity,
                "itemIndex": item_index,
                "shop": shop_label,
                "name": item_name,
                "category": category,
                "priceModifier": attributes["PriceModifier"],
                "quantityPerPurchase": attributes["QuantityPerPurchase"],
                "totalAvailableQuantity": attributes["TotalAvailableQuantity"],
                "project": project,
                "_offsets": offsets,
            })
    return records


def _shop_paths(relative_value: str) -> tuple[PurePosixPath, Path, Path, Path]:
    relative = safe_relative(relative_value)
    if relative.suffix.casefold() != ".wgd" or not relative.parts \
            or relative.parts[0].casefold() != "gringores":
        raise ValueError("Shop source must be one prepared Gringo dictionary")
    raw = under(GRINGO_UNPACKED_ROOT, relative)
    packed = under(GRINGO_PACKED_ROOT, relative)
    project = under(GRINGO_OVERRIDE_ROOT, relative)
    if not raw.is_file() or not packed.is_file():
        raise FileNotFoundError(f"Prepared shop dictionary is missing: {relative.as_posix()}")
    return relative, raw, packed, project


def _run_resource_tool(arguments: list[str], timeout: int = 30) -> None:
    result = subprocess.run(
        [str(paths.RPF6_TOOL), *arguments],
        cwd=str(paths.RPF6_TOOL.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"RPF6 resource operation failed: {detail}")


def _active_shop_bytes(raw: Path, project: Path) -> bytes:
    if not project.is_file():
        return raw.read_bytes()
    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-shop-read-") as temp_name:
        target = Path(temp_name) / "shop.wgd.raw"
        _run_resource_tool(["resource-unpack", str(project), str(target)])
        return target.read_bytes()


def shops_payload(vanilla_only: bool = False) -> dict:
    rows = []
    if GRINGO_UNPACKED_ROOT.is_dir():
        for raw in sorted(GRINGO_UNPACKED_ROOT.rglob("*.wgd")):
            relative = PurePosixPath(raw.relative_to(GRINGO_UNPACKED_ROOT).as_posix())
            _relative, _raw, packed, project = _shop_paths(relative.as_posix())
            data = raw.read_bytes() if vanilla_only else _active_shop_bytes(raw, project)
            source_rows = _shop_records(data, relative, project.is_file() and not vanilla_only)
            for row in source_rows:
                row.pop("_offsets", None)
                row["sourcePath"] = str(packed)
                row["projectPath"] = str(project)
            rows.extend(source_rows)
    shop_ids = {f'{row["source"]}|{row["rootHash"]}' for row in rows}
    return {
        "rows": rows,
        "counts": {
            "items": len(rows),
            "shops": len(shop_ids),
            "project": sum(row["project"] for row in rows),
        },
    }


def save_shop(source: str, root_hash: str, item_index: int,
              expected_name: str, edits: list[dict]) -> dict:
    _integer(item_index, "Shop item index", 0, 2147483647)
    relative, raw, packed, project = _shop_paths(source)
    data = bytearray(_active_shop_bytes(raw, project))
    records = _shop_records(data, relative, project.is_file())
    record = next((row for row in records
                   if row["rootHash"] == root_hash.upper()
                   and row["itemIndex"] == item_index), None)
    if record is None or record["name"] != expected_name:
        raise ValueError("The shop source changed; reload the item before saving")
    allowed = {
        "PriceModifier": ("priceModifier", "float"),
        "QuantityPerPurchase": ("quantityPerPurchase", "int"),
        "TotalAvailableQuantity": ("totalAvailableQuantity", "int"),
    }
    wanted = {}
    for edit in _edit_list(edits):
        field = str(edit.get("field", ""))
        if field not in allowed or field in wanted:
            raise ValueError("Each supported shop field must be named once")
        key, kind = allowed[field]
        value = edit.get("value")
        if field not in record["_offsets"]:
            raise ValueError(f"This shop record has no editable {field}")
        if kind == "float":
            parsed = _number(value, "PriceModifier", 0, 1000)
            # WGD stores IEEE float32. Compare the encoded value, not float64 input.
            parsed = struct.unpack("<f", struct.pack("<f", parsed))[0]
        else:
            minimum = 0 if field == "QuantityPerPurchase" else -1
            parsed = int(_number(value, field, minimum, 2147483647, integer=True))
        wanted[field] = (key, kind, parsed)
    changed = 0
    for field, (key, kind, value) in wanted.items():
        if value == record[key]:
            continue
        offset = record["_offsets"][field]
        if kind == "float":
            struct.pack_into("<f", data, offset, value)
        else:
            struct.pack_into("<i", data, offset, value)
        changed += 1
    if not changed:
        return {"saved": 0, "projectPath": str(project), "backup": ""}

    with tempfile.TemporaryDirectory(prefix="lexeditor-rdr-shop-save-") as temp_name:
        temporary_root = Path(temp_name)
        unpacked = temporary_root / "shop.wgd.raw"
        output = temporary_root / "shop.wgd"
        unpacked.write_bytes(data)
        template = project if project.is_file() else packed
        _run_resource_tool([
            "resource-pack", str(template), str(unpacked), str(output),
        ])
        # Never publish an unverified repack. Unpack the temporary candidate and
        # compare every byte, including fields/components that were not edited.
        verified_data = _active_shop_bytes(raw, output)
        if verified_data != bytes(data):
            raise RuntimeError("Packed shop verification failed; project override was not changed")
        payload = output.read_bytes()
    backup = backup_file(project)
    atomic_bytes(project, payload)
    return {
        "saved": changed,
        "source": relative.as_posix(),
        "rootHash": root_hash.upper(),
        "itemIndex": item_index,
        "projectPath": str(project),
        "backup": str(backup) if backup else "",
        "sourceUnchanged": sha256_file(packed),
    }


def _decode_preserved(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252"), "cp1252"


def _split_value_suffix(value: str) -> tuple[str, str]:
    match = re.search(r"(?P<suffix>\s+[;#].*)$", value)
    if match is None:
        return value.rstrip(), value[len(value.rstrip()):]
    authored = value[:match.start()].rstrip()
    return authored, value[len(authored):]


def _parse_ini(text: str) -> tuple[list[dict], dict[tuple[str, str], dict]]:
    sections = []
    by_section = {}
    final = {}
    current = None
    comments = []
    for index, raw_line in enumerate(text.splitlines(keepends=True)):
        content = raw_line.rstrip("\r\n")
        stripped = content.strip()
        if stripped.startswith((";", "#")):
            comments.append(stripped.lstrip(";# "))
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            name = stripped[1:-1].strip()
            identity = name.casefold()
            current = by_section.get(identity)
            if current is None:
                current = {"name": name, "help": " ".join(comments), "settings": []}
                sections.append(current)
                by_section[identity] = current
            comments = []
            continue
        match = INI_SETTING.match(content)
        if current is not None and match is not None:
            prefix = match.group("prefix")
            key = prefix.split("=", 1)[0].strip()
            value, suffix = _split_value_suffix(match.group("value"))
            record = {
                "section": current["name"],
                "key": key,
                "value": value.strip(),
                "help": " ".join(comments),
                "line": index,
                "prefix": prefix,
                "suffix": suffix,
            }
            identity = (current["name"].casefold(), key.casefold())
            if identity in final:
                prior = final[identity]
                current["settings"].remove(prior)
            current["settings"].append(record)
            final[identity] = record
            comments = []
        elif not stripped:
            comments = []
    return sections, final


def settings_payload() -> dict:
    if not SETTINGS_FILE.is_file():
        return {"available": False, "file": str(SETTINGS_FILE), "sections": []}
    text, encoding = _decode_preserved(SETTINGS_FILE)
    sections, _final = _parse_ini(text)
    for section in sections:
        for setting in section["settings"]:
            lowered = setting["value"].casefold()
            identity = (section["name"].casefold(), setting["key"].casefold())
            if lowered in {"true", "false"}:
                setting["control"] = "checkbox"
            elif identity in SETTING_CONTROLS:
                setting.update(SETTING_CONTROLS[identity])
            else:
                setting["control"] = "text"
            setting.pop("line", None)
            setting.pop("prefix", None)
            setting.pop("suffix", None)
    return {
        "available": True,
        "file": str(SETTINGS_FILE),
        "encoding": encoding,
        "sections": sections,
    }


def save_settings(edits: list[dict]) -> dict:
    if not SETTINGS_FILE.is_file():
        raise FileNotFoundError(f"RDR settings file not found: {SETTINGS_FILE}")
    text, encoding = _decode_preserved(SETTINGS_FILE)
    lines = text.splitlines(keepends=True)
    _sections, final = _parse_ini(text)
    wanted = {}
    for edit in _edit_list(edits):
        section = str(edit.get("section", ""))
        key = str(edit.get("key", ""))
        value = str(edit.get("value", ""))
        if not section or not key or "\x00" in value or "\r" in value or "\n" in value:
            raise ValueError("Each INI edit needs one section, key, and single-line value")
        identity = (section.casefold(), key.casefold())
        if identity in wanted:
            raise ValueError(f"Duplicate INI edit: {section}/{key}")
        wanted[identity] = value
    missing = set(wanted) - set(final)
    if missing:
        raise ValueError("Unknown INI setting(s): " + ", ".join(
            f"{section}/{key}" for section, key in sorted(missing)))
    for identity, value in wanted.items():
        original = final[identity]["value"]
        label = "/".join(identity)
        if original.casefold() in {"true", "false"}:
            value = _validate_scalar(original, "bool", value, label)
        elif identity in SETTING_CONTROLS:
            limits = SETTING_CONTROLS[identity]
            _number(value, label, limits["minimum"], limits["maximum"],
                    integer=limits.get("step") == 1)
        wanted[identity] = value.strip()
    changed = 0
    for identity, value in wanted.items():
        record = final[identity]
        if value == record["value"]:
            continue
        line = lines[record["line"]]
        ending = line[len(line.rstrip("\r\n")):]
        lines[record["line"]] = record["prefix"] + value + record["suffix"] + ending
        changed += 1
    if not changed:
        return {"saved": 0, "file": str(SETTINGS_FILE), "backup": ""}
    candidate = "".join(lines)
    _sections, parsed = _parse_ini(candidate)
    if any(parsed.get(identity, {}).get("value") != value for identity, value in wanted.items()):
        raise ValueError("INI edit changes the setting structure; no settings were written")
    payload = candidate.encode(encoding)
    backup = backup_file(SETTINGS_FILE)
    atomic_bytes(SETTINGS_FILE, payload)
    reread = settings_payload()
    actual = {(section["name"].casefold(), setting["key"].casefold()): setting["value"]
              for section in reread["sections"] for setting in section["settings"]}
    if any(actual.get(identity) != value for identity, value in wanted.items()):
        raise RuntimeError("One or more INI values did not read back")
    return {
        "saved": changed,
        "file": str(SETTINGS_FILE),
        "backup": str(backup) if backup else "",
    }


def _integer(value, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def validate_loot_document(document: dict) -> None:
    if not isinstance(document, dict) or type(document.get("schemaVersion")) is not int or document["schemaVersion"] != 1:
        raise ValueError("Unsupported LexerRDR loot schema; expected schemaVersion 1")
    if document.get("contract") != "LexerRDR.loot":
        raise ValueError("Unsupported LexerRDR loot contract")
    bonus = document.get("corpseBonusItem")
    if not isinstance(bonus, dict):
        raise ValueError("Missing corpseBonusItem object")
    _integer(bonus.get("chancePercent"), "corpseBonusItem.chancePercent", 0, 100)
    entries = bonus.get("entries")
    if not isinstance(entries, list) or len(entries) != 5:
        raise ValueError("corpseBonusItem.entries must contain the five proven item IDs")
    identifiers = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each corpse bonus entry must be an object")
        identifiers.append(_integer(entry.get("itemEnum"), "itemEnum", 0, 275))
        _integer(entry.get("quantity"), f"item {identifiers[-1]} quantity", 0, 100000)
        _integer(entry.get("weight"), f"item {identifiers[-1]} weight", 0, 100000)
    if set(identifiers) != {1, 2, 6, 7, 8} or len(set(identifiers)) != 5:
        raise ValueError("Unknown corpse bonus item ID; allowed IDs are 1, 2, 6, 7, and 8")
    money = document.get("money")
    base = money.get("baseRoll") if isinstance(money, dict) else None
    if not isinstance(base, dict):
        raise ValueError("Missing money.baseRoll object")
    for flag in ("applyStatScale", "applyItem17Multiplier", "applyFinalMultiplier"):
        if not isinstance(base.get(flag), bool):
            raise ValueError(f"money.baseRoll.{flag} must be true or false")
    value_range = base.get("range")
    if not isinstance(value_range, dict):
        raise ValueError("Missing money.baseRoll.range object")
    minimum = _number(value_range.get("minimum"), "Money minimum", 0, 100000)
    maximum = _number(value_range.get("maximum"), "Money maximum", 0, 100000)
    if minimum > maximum:
        raise ValueError("Money range must be ordered and non-negative")
    paths = money.get("decoratorPaths")
    expected_paths = {
        ("NoMoney", "suppress"),
        ("iAdditionalMoney", "base-plus-decorator"),
        ("nOnlyMoney", "decorator-only"),
    }
    if (not isinstance(paths, list) or len(paths) != len(expected_paths)
            or any(not isinstance(path, dict) for path in paths)):
        raise ValueError("Money decorator paths must contain exactly the three proven paths")
    actual_paths = {(path.get("decorator"), path.get("operation")) for path in paths}
    if actual_paths != expected_paths:
        raise ValueError("Money decorator paths do not match the proven WSC contract")


def loot_payload() -> dict:
    if not LOOT_FILE.is_file():
        return {
            "available": False,
            "file": str(LOOT_FILE),
            "label": "ASI override",
            "reason": "LexerRDR.loot.json is not present in the RDR project.",
        }
    document = json.loads(LOOT_FILE.read_text(encoding="utf-8-sig"))
    validate_loot_document(document)
    return {
        "available": True,
        "file": str(LOOT_FILE),
        "label": "ASI override",
        "document": document,
    }


def save_loot(document: dict) -> dict:
    validate_loot_document(document)
    payload = (json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    backup = backup_file(LOOT_FILE)
    atomic_bytes(LOOT_FILE, payload)
    reread = json.loads(LOOT_FILE.read_text(encoding="utf-8"))
    validate_loot_document(reread)
    if reread != document:
        raise RuntimeError("LexerRDR loot override did not read back")
    return {
        "saved": 1,
        "file": str(LOOT_FILE),
        "backup": str(backup) if backup else "",
    }


def missions_payload(vanilla_only: bool = False) -> dict:
    base = mission_rewards.load_generated()
    override = {
        "schemaVersion": 1,
        "contract": "LexerRDR.mission-rewards",
        "overrides": [],
    }
    if mission_rewards.OVERRIDE_FILE.is_file() and not vanilla_only:
        override = mission_rewards.validate_override(json.loads(
            mission_rewards.OVERRIDE_FILE.read_text(encoding="utf-8-sig")), base)
    by_id = {row["id"]: row["rewards"] for row in override["overrides"]}
    rows = []
    for source in base["missions"]:
        row = dict(source)
        base_rewards = dict(source["rewards"])
        override_rewards = dict(by_id.get(source["id"], {}))
        row["baseRewards"] = base_rewards
        row["overrideRewards"] = override_rewards
        row["rewards"] = {**base_rewards, **override_rewards}
        row["project"] = bool(override_rewards)
        rows.append(row)
    return {
        "schemaVersion": base["schemaVersion"],
        "contract": base["contract"],
        "summary": {**base["summary"],
                    "projectMissions": len(by_id),
                    "projectFields": sum(len(value) for value in by_id.values())},
        "sources": base["sources"],
        "limits": base["limits"],
        "missions": rows,
        "overrideFile": str(mission_rewards.OVERRIDE_FILE),
    }


def save_missions(document: dict) -> dict:
    base = mission_rewards.load_generated()
    normalized = mission_rewards.validate_override(document, base)
    base_by_id = {row["id"]: row["rewards"] for row in base["missions"]}
    changed_rows = []
    for row in normalized["overrides"]:
        changed = {
            reward: value for reward, value in row["rewards"].items()
            if value != base_by_id[row["id"]][reward]
        }
        if changed:
            changed_rows.append({"id": row["id"], "rewards": changed})
    payload_document = mission_rewards.validate_override({
        "schemaVersion": 1,
        "contract": "LexerRDR.mission-rewards",
        "overrides": changed_rows,
    }, base)
    payload = (json.dumps(payload_document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    backup = backup_file(mission_rewards.OVERRIDE_FILE)
    atomic_bytes(mission_rewards.OVERRIDE_FILE, payload)
    reread = mission_rewards.validate_override(json.loads(
        mission_rewards.OVERRIDE_FILE.read_text(encoding="utf-8")), base)
    if reread != payload_document:
        raise RuntimeError("Mission reward overrides did not read back")
    return {
        "saved": sum(len(row["rewards"]) for row in changed_rows),
        "missions": len(changed_rows),
        "file": str(mission_rewards.OVERRIDE_FILE),
        "backup": str(backup) if backup else "",
        "sources": base["sources"],
    }


def redhook_payload() -> dict:
    missing = [name for name in REDHOOK_FILES if not (GAME_ROOT / name).is_file()]
    ini = GAME_ROOT / "RedHook.ini"
    intro = {
        "available": False,
        "enabled": False,
        "file": str(ini),
        "problem": "RedHook.ini is not installed",
    }
    if ini.is_file():
        try:
            text, _encoding = _decode_preserved(ini)
            match = REDHOOK_SKIP_INTRO.search(text)
            if match is None:
                intro["problem"] = "SkipIntroLogos is not present in RedHook.ini"
            else:
                value = match.group("value").strip().casefold()
                intro = {
                    "available": True,
                    "enabled": value in {"1", "true", "yes", "on"},
                    "file": str(ini),
                    "problem": "" if value in {"1", "true", "yes", "on"}
                    else "SkipIntroLogos is disabled",
                }
        except OSError as error:
            intro["problem"] = f"RedHook.ini could not be read: {error}"
    return {
        "installed": not missing,
        "missing": missing,
        "required": list(REDHOOK_FILES),
        "gameRoot": str(GAME_ROOT),
        "url": REDHOOK_URL,
        "skipIntroLogos": intro,
    }


def configure_redhook() -> dict:
    status = redhook_payload()
    if not status["installed"]:
        raise FileNotFoundError(
            "RedHook must be installed before its startup-logo setting can be changed")
    ini = GAME_ROOT / "RedHook.ini"
    text, encoding = _decode_preserved(ini)
    match = REDHOOK_SKIP_INTRO.search(text)
    if match is None:
        raise ValueError(
            "The installed RedHook.ini has no SkipIntroLogos setting; reinstall official RedHook v0.8")
    if match.group("value").strip().casefold() in {"1", "true", "yes", "on"}:
        return {**status, "changed": 0, "backup": ""}

    updated = text[:match.start()] + match.group("prefix") + "true" + \
        match.group("suffix") + text[match.end():]
    backup = backup_file(ini)
    atomic_bytes(ini, updated.encode(encoding))
    reread = redhook_payload()
    if not reread["skipIntroLogos"]["enabled"]:
        raise RuntimeError("SkipIntroLogos did not read back as enabled")
    return {
        **reread,
        "changed": 1,
        "backup": str(backup) if backup else "",
    }


def open_redhook_page() -> dict:
    status = redhook_payload()
    if os.environ.get("LEXEDITOR_RDR_OPEN_URL_DRY_RUN", "0") == "1":
        return {**status, "opened": False, "dryRun": True}
    opened = bool(webbrowser.open(REDHOOK_URL, new=2, autoraise=True))
    if not opened:
        raise RuntimeError("Windows could not open the official RedHook page")
    return {**status, "opened": True, "dryRun": False}


def _normalize_data_map_rows(rows) -> list[dict]:
    if not isinstance(rows, list):
        raise ValueError("RDR data map rows must be a list")
    normalized = []
    for index, source in enumerate(rows):
        if not isinstance(source, dict):
            raise ValueError(f"RDR data map row {index + 1} must be an object")
        filename = str(source.get("filename") or source.get("file") or "").strip()
        if not filename:
            raise ValueError(f"RDR data map row {index + 1} has no filename")
        status = str(source.get("status", "not-integrated")).strip().casefold()
        if status not in {"integrated", "partial", "not-integrated"}:
            status = "not-integrated"
        target_value = source.get("target")
        target = str(target_value).strip() if target_value else ""
        normalized.append({
            "filename": filename,
            "controls": str(source.get("controls") or source.get("system") or "").strip(),
            "notes": str(source.get("notes") or source.get("description") or "").strip(),
            "status": status,
            "target": target,
            "openable": bool(source.get("openable", target)) and bool(target),
            "openLabel": str(source.get("openLabel") or "Open its format-specific editor"),
        })
    normalized.sort(key=lambda row: row["filename"].casefold())
    return normalized


def _provisional_data_map_rows() -> list[dict]:
    rows = []
    if PREPARED_ROOT.is_dir():
        for source in PREPARED_ROOT.rglob("*"):
            if source.is_file():
                rows.append({
                    "filename": source.relative_to(PREPARED_ROOT).as_posix(),
                    "controls": "Prepared tuning data",
                    "notes": "Prepared from tune_d11generic.rpf; a format-specific editor is not mapped yet.",
                    "status": "not-integrated",
                })
    for source_id, definition in INVENTORY_SOURCES.items():
        rows.append({
            "filename": definition["relative"].as_posix(),
            "controls": f'{definition["label"]} inventory records',
            "notes": "Direct scalar item fields are available in the Items editor.",
            "status": "integrated",
            "target": "items",
            "openable": True,
        })
    if GRINGO_UNPACKED_ROOT.is_dir():
        for source in GRINGO_UNPACKED_ROOT.rglob("*.wgd"):
            rows.append({
                "filename": "gringores/" + source.relative_to(GRINGO_UNPACKED_ROOT).as_posix(),
                "controls": "Shop inventory and shopkeeper interaction records",
                "notes": "ShopInventory price, purchase quantity, and stock fields are available in Shops.",
                "status": "partial",
                "target": "shops",
                "openable": True,
            })
    rows.extend((
        {"filename": "LexerRDR.ini", "controls": "LexerRDR runtime settings",
         "notes": "Typed project settings are available in Settings.", "status": "integrated",
         "target": "settings", "openable": True},
        {"filename": "LexerRDR.loot.json", "controls": "ASI corpse item and money overrides",
         "notes": "Schema-validated loot controls are available in Loot Tables.", "status": "integrated",
         "target": "loot", "openable": True},
    ))
    return _normalize_data_map_rows(rows)


def data_map_payload() -> dict:
    if DATA_MAP_FILE.is_file():
        document = json.loads(DATA_MAP_FILE.read_text(encoding="utf-8-sig"))
        source_rows = document.get("rows", document.get("files", [])) if isinstance(document, dict) else document
        rows = _normalize_data_map_rows(source_rows)
        metadata = dict(document) if isinstance(document, dict) else {}
        metadata.update({"rows": rows, "source": str(DATA_MAP_FILE),
                         "provisional": bool(metadata.get("provisional", False))})
        return metadata
    return {
        "rows": _provisional_data_map_rows(),
        "source": str(DATA_MAP_FILE),
        "provisional": True,
    }


def dashboard_payload() -> dict:
    manifest = {}
    manifest_path = EXTRACT_ROOT / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        pass
    return {
        "paths": {
            "Project": str(PROJECT),
            "Editable overrides": str(OVERRIDE_ROOT),
            "Inventory overrides": str(CONTENT_OVERRIDE_ROOT),
            "Shop overrides": str(GRINGO_OVERRIDE_ROOT),
            "Mission ASI override": str(mission_rewards.OVERRIDE_FILE),
            "Settings": str(SETTINGS_FILE),
            "Loot ASI override": str(LOOT_FILE),
            "Installed game": str(GAME_ROOT),
            "Prepared vanilla data": str(PREPARED_ROOT),
            "Prepared inventory data": str(CONTENT_PREPARED_ROOT),
            "Prepared shop data": str(GRINGO_UNPACKED_ROOT),
        },
        "manifest": manifest,
        "redHook": redhook_payload(),
        "problems": paths.check()
        + ([] if PREPARED_ROOT.is_dir() else [f"Prepared RDR data is missing: {PREPARED_ROOT}"])
        + ([] if CONTENT_PREPARED_ROOT.is_dir() else [
            f"Prepared RDR inventory data is missing: {CONTENT_PREPARED_ROOT}"])
        + ([] if GRINGO_UNPACKED_ROOT.is_dir() else [
            f"Prepared RDR shop data is missing: {GRINGO_UNPACKED_ROOT}"])
        + ([] if SETTINGS_FILE.is_file() else [f"Project settings are missing: {SETTINGS_FILE}"])
        + ([] if LOOT_FILE.is_file() else [f"Loot ASI override is missing: {LOOT_FILE}"]),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LexeditorRDR/1.0"

    def log_message(self, _format, *_args):
        return

    def json_response(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def file_response(self, path: Path) -> None:
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_TEXT_BYTES * 2:
            raise ValueError("Request body is too large")
        def reject_constant(value):
            raise ValueError(f"Invalid JSON number: {value}")
        document = json.loads(self.rfile.read(length).decode("utf-8"),
                              parse_constant=reject_constant) if length else {}
        if not isinstance(document, dict):
            raise ValueError("Request body must be a JSON object")
        return document

    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        try:
            if path == "/":
                self.file_response(PLUGIN_ROOT / "editor.html")
            elif path.startswith("/shared/"):
                shared_root = (LEXEDITOR_ROOT / "ui").resolve()
                target = (shared_root / path.removeprefix("/shared/")).resolve()
                if shared_root not in target.parents or not target.is_file():
                    self.json_response({"error": "shared UI asset not found"}, 404)
                else:
                    self.file_response(target)
            elif path.startswith("/fonts/"):
                name = Path(path.removeprefix("/fonts/")).name
                candidates = (
                    PLUGIN_ROOT / "assets" / "fonts" / name,
                    paths.RDR2_FONT_ROOT / name,
                )
                target = next((candidate for candidate in candidates if candidate.is_file()), None)
                if target is None:
                    self.json_response({"error": "font not found"}, 404)
                else:
                    self.file_response(target)
            elif path == "/api/plugin":
                self.json_response({
                    "apiVersion": 1,
                    "pluginId": "rdr",
                    "name": "Red Dead Redemption",
                    "hosted": HOSTED,
                    "windowHost": WINDOW_HOST,
                    "projectRoot": str(PROJECT),
                    "editorRoot": str(PLUGIN_ROOT),
                    "capabilities": [
                        "prepared-files", "project-overrides", "source-editor",
                        "items", "shops", "missions", "loot-asi-override", "settings",
                        "data-map", "redhook-prerequisite", "github-workspace",
                    ],
                })
            elif path == "/api/dashboard":
                self.json_response(dashboard_payload())
            elif path == "/api/files":
                self.json_response(files_payload())
            elif path == "/api/file":
                self.json_response(read_file(query.get("path", [""])[0]))
            elif path == "/api/items":
                self.json_response(items_payload(query.get("dataset", ["current"])[0] == "vanilla"))
            elif path == "/api/shops":
                self.json_response(shops_payload(query.get("dataset", ["current"])[0] == "vanilla"))
            elif path == "/api/loot":
                self.json_response(loot_payload())
            elif path == "/api/missions":
                self.json_response(missions_payload(query.get("dataset", ["current"])[0] == "vanilla"))
            elif path == "/api/settings":
                self.json_response(settings_payload())
            elif path in {"/api/datamap", "/api/data-map"}:
                self.json_response(data_map_payload())
            else:
                self.json_response({"error": "not found"}, 404)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.body()
            if path == "/api/file/save":
                self.json_response(save_file(
                    str(body.get("path", "")),
                    str(body.get("text", "")),
                    str(body.get("encoding", "utf-8")),
                ))
            elif path == "/api/item/save":
                self.json_response(save_item(
                    str(body.get("source", "")),
                    body.get("index", -1),
                    str(body.get("expectedName", "")),
                    body.get("edits", []),
                ))
            elif path == "/api/shop/save":
                self.json_response(save_shop(
                    str(body.get("source", "")),
                    str(body.get("rootHash", "")),
                    body.get("itemIndex", -1),
                    str(body.get("expectedName", "")),
                    body.get("edits", []),
                ))
            elif path == "/api/loot/save":
                self.json_response(save_loot(body.get("document")))
            elif path == "/api/missions/save":
                self.json_response(save_missions(body.get("document", body)))
            elif path == "/api/settings/save":
                self.json_response(save_settings(body.get("edits", [])))
            elif path == "/api/redhook/open":
                self.json_response(open_redhook_page())
            elif path == "/api/redhook/configure":
                self.json_response(configure_redhook())
            else:
                self.json_response({"error": "not found"}, 404)
        except Exception as error:
            self.json_response({"error": str(error)}, 400)


def create_server(port=PORT):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    create_server().serve_forever()
