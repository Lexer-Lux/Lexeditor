"""Safe reader and project-overlay writer for Memoria's FF9 CSV formats."""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from . import paths
from .memoria_baseline import ensure as ensure_baseline


@dataclass(frozen=True)
class Dataset:
    key: str
    tab: str
    label: str
    relative_path: str
    controls: str
    filter_column: str | None = None
    filter_value: str | None = None


def _dataset(key: str, tab: str, label: str, path: str, controls: str | None = None) -> Dataset:
    return Dataset(key, tab, label, path, controls or label)


# Every CSV shipped in the pinned Memoria baseline. Keep this surface exact: the
# Data Map and editor catalog are generated from it rather than maintained twice.
_BASE = [
    ("items", "items", "Items", "Items/Items.csv", "Item identity, prices, equipment classes, abilities, and usability"),
    ("weapons", "weapons", "Weapons", "Items/Weapons.csv", "Weapon category, model, script, power, elements, rate, and sound"),
    ("armor", "armor", "Armor", "Items/Armors.csv", "Physical and magical defence and evasion"),
    ("item-effects", "items", "Item effects", "Items/ItemEffects.csv", "Targeting, script, power, rate, element, and status"),
    ("initial-items", "items", "Initial inventory", "Items/InitialItems.csv", "Starting item IDs and quantities"),
    ("mix-items", "synthesis", "Mix recipes", "Items/MixItems.csv", "Mix recipe results and ingredients"),
    ("item-stats", "items", "Equipment stats", "Items/Stats.csv", "Equipment stat bonuses and elemental properties"),
    ("shops", "shops", "Shop inventories", "Items/ShopItems.csv", "Shop IDs and ordered item inventories"),
    ("synthesis", "synthesis", "Synthesis recipes", "Items/Synthesis.csv", "Recipe shops, price, result, and ingredients"),
    ("abilities", "abilities", "Support abilities", "Characters/Abilities/AbilityGems.csv", "Support-ability gem costs and boosted versions"),
    ("characters", "characters", "Character base stats", "Characters/BaseStats.csv", "Base dexterity, strength, magic, will, and gem capacity"),
    ("battle-parameters", "characters", "Battle parameters", "Characters/BattleParameters.csv", "Models, animations, battle geometry, status anchors, and weapon sounds"),
    ("character-parameters", "characters", "Character parameters", "Characters/CharacterParameters.csv", "Starting row, victory pose, category, command/equipment sets, model formula, and name keyword"),
    ("command-sets", "characters", "Command sets", "Characters/CommandSets.csv", "Per-character command set assignments"),
    ("commands", "characters", "Commands", "Characters/Commands.csv", "Battle command types and ability lists"),
    ("default-equipment", "characters", "Starting equipment", "Characters/DefaultEquipment.csv", "Initial weapon, headgear, wristwear, armor, and accessory"),
    ("leveling", "characters", "Level growth", "Characters/Leveling.csv", "Experience thresholds and HP/MP growth for levels 1 through 99"),
    ("actions", "magic", "Battle actions", "Battle/Actions.csv", "Battle action targeting, animation, script, power, status, MP, and type"),
    ("magic-sword-sets", "magic", "Magic Sword sets", "Battle/MagicSwordSets.csv", "Supporter, beneficiary, and ability-set mapping"),
    ("status-data", "magic", "Status data", "Battle/StatusData.csv", "Status priority, timing, colors, and tick behavior"),
    ("status-sets", "magic", "Status sets", "Battle/StatusSets.csv", "Named status-set membership"),
    ("sfx-shp", "effects", "SHP definitions", "SpecialEffects/Common/SHP.csv", "Shape-particle definitions and textures"),
    ("sfx-sps", "effects", "SPS definitions", "SpecialEffects/Common/SPS.csv", "Sprite-particle definitions, textures, colors, and timing"),
    ("tetra-cards", "tetra-master", "Tetra Master cards", "TetraMaster/TripleTriad.csv", "Card attack, defence, type, and arrow data"),
    ("world-transport", "world", "Transport controls", "World/TransportControls.csv", "World transport movement and collision parameters"),
    ("world-weather", "world", "Weather colors", "World/WeatherColors.csv", "World light, fog, and ambient weather colors"),
]
_ABILITY_NAMES = [
    "Amarant", "Beatrix1", "Beatrix2", "Blank1", "Blank2", "Cinna1", "Cinna2",
    "Eiko", "Freya", "Garnet", "Marcus1", "Marcus2", "Quina", "Steiner", "Vivi", "Zidane",
]
DATASETS = tuple(_dataset(*row) for row in _BASE) + tuple(
    _dataset(f"ability-{name.lower().replace('1','-1').replace('2','-2')}", "abilities",
             f"{re.sub(r'([A-Za-z]+)([12])$', r'\\1 abilities \\2', name) if name[-1:].isdigit() else name + ' abilities'}",
             f"Characters/Abilities/{name}.csv", "Ability IDs and AP requirements")
    for name in _ABILITY_NAMES
)
DATASET_BY_KEY = {dataset.key: dataset for dataset in DATASETS}

_INTEGER_RANGES = {
    "byte": (0, 255), "uint8": (0, 255), "sbyte": (-128, 127), "int8": (-128, 127),
    "uint16": (0, 65535), "int16": (-32768, 32767),
    "uint32": (0, 4294967295), "int32": (-2147483648, 2147483647),
    "uint64": (0, 9007199254740991), "int64": (-9007199254740991, 9007199254740991),
}
_BOOLEAN_TYPES = {"bit", "bool", "boolean"}
_FLOAT_TYPES = {"single", "float", "double"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse(line: str) -> list[str]:
    return next(csv.reader([line], delimiter=";", quotechar='"'))


def _encode_row(values: list[str]) -> str:
    output = io.StringIO(newline="")
    csv.writer(output, delimiter=";", quotechar='"', lineterminator="").writerow(values)
    return output.getvalue()


def _comment_text(values: list[str]) -> str:
    text = " ".join(value for value in values if value).strip()
    text = re.sub(r"^#\s*", "", text)
    text = re.sub(r"^\d+\s*-\s*", "", text)
    return text.strip()


class MemoriaCsvDocument:
    def __init__(self, path: Path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        if raw.startswith(b"\xef\xbb\xbf"):
            self.encoding, text = "utf-8-sig", raw.decode("utf-8-sig")
        else:
            try:
                self.encoding, text = "utf-8", raw.decode("utf-8")
            except UnicodeDecodeError:
                self.encoding, text = "cp1252", raw.decode("cp1252")
        kept = text.splitlines(keepends=True)
        self.lines = [line.rstrip("\r\n") for line in kept]
        self.endings = [line[len(line.rstrip("\r\n")):] for line in kept]
        self.columns, self.types = self._find_schema()
        self.rows = self._read_rows()
        self.fields = self._describe_fields()

    def _find_schema(self) -> tuple[list[str], list[str]]:
        for index, line in enumerate(self.lines[:-1]):
            if not line.startswith("#") or ";" not in line or line.startswith("#!"):
                continue
            columns = [value.strip() for value in _parse(line[1:].strip())]
            type_line = self.lines[index + 1]
            if not type_line.startswith("#") or ";" not in type_line or type_line.startswith("#!"):
                continue
            types = [value.strip() for value in _parse(type_line[1:].strip())]
            width = 0
            for candidate in self.lines[index + 2:]:
                if candidate and not candidate.lstrip().startswith("#"):
                    values = _parse(candidate)
                    width = next((i for i, value in enumerate(values) if value.lstrip().startswith("#")), len(values))
                    break
            if width and width <= len(columns) and width <= len(types):
                columns, types = columns[:width], types[:width]
            while columns and not columns[-1]:
                columns.pop()
            types = types[:len(columns)]
            if len(columns) >= 2 and len(types) == len(columns):
                if len(set(columns)) != len(columns) or any(not name for name in columns):
                    raise ValueError(f"Memoria CSV has duplicate or empty column names: {self.path}")
                return columns, types
        raise ValueError(f"Memoria CSV schema header was not found: {self.path}")

    def _read_rows(self) -> list[dict[str, Any]]:
        rows = []
        for line_number, line in enumerate(self.lines):
            if not line or line.lstrip().startswith("#"):
                continue
            values = _parse(line)
            if len(values) < len(self.columns):
                raise ValueError(f"Line {line_number + 1} has fewer fields than its schema: {self.path}")
            data, suffix = values[:len(self.columns)], values[len(self.columns):]
            by_name = dict(zip(self.columns, data))
            identity = by_name.get("Id", by_name.get("id", str(len(rows))))
            name = by_name.get("Comment") or by_name.get("Name") or _comment_text(suffix)
            rows.append({"line": line_number, "id": identity, "name": name or f"Record {identity}",
                         "raw": by_name, "suffix": suffix})
        return rows

    def _describe_fields(self) -> list[dict[str, Any]]:
        result = []
        for column, declared in zip(self.columns, self.types):
            normalized = declared.strip().casefold()
            values = [row["raw"][column].strip() for row in self.rows]
            field: dict[str, Any] = {"key": column, "label": column.replace("_", " "),
                                     "declaredType": declared or "String",
                                     "editable": column.casefold() != "id"}
            if normalized in _BOOLEAN_TYPES:
                field["kind"] = "boolean"
            elif normalized in _INTEGER_RANGES:
                if any(value and not re.fullmatch(r"[-+]?\d+", value) for value in values):
                    field.update(kind="stored", editable=False)
                else:
                    low, high = _INTEGER_RANGES[normalized]
                    field.update(kind="integer", min=low, max=high)
            elif normalized in _FLOAT_TYPES:
                field.update(kind="number", step="any")
            elif "[" in normalized or "{" in normalized:
                field.update(kind="stored", editable=False)
            elif normalized in {"string", ""}:
                field["kind"] = "text"
            else:
                field.update(kind="stored", editable=False)
            result.append(field)
        return result

    def public_rows(self, dataset: Dataset) -> list[dict[str, Any]]:
        rows = self.rows
        if dataset.filter_column:
            rows = [row for row in rows if row["raw"].get(dataset.filter_column) == dataset.filter_value]
        fields = {field["key"]: field for field in self.fields}
        has_id = any(key.casefold() == "id" for key in self.columns)
        return [{"line": row["line"],
                 "id": (int(row["id"]) if has_id and str(row["id"]).lstrip("-+").isdigit()
                        else row["id"] if has_id else index + 1),
                 "name": row["name"],
                 "values": {key: self._public_value(value, fields[key]) for key, value in row["raw"].items()}}
                for index, row in enumerate(rows)]

    @staticmethod
    def _public_value(raw: str, field: dict[str, Any]) -> Any:
        if field["kind"] == "boolean":
            return raw.strip().casefold() in {"1", "true"}
        if field["kind"] == "integer" and raw.strip():
            return int(raw)
        if field["kind"] == "number" and raw.strip():
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError(f"{field['key']} contains a non-finite number")
            return value
        return raw

    def apply(self, changes: list[dict[str, Any]]) -> None:
        rows = {row["line"]: row for row in self.rows}
        fields = {field["key"]: field for field in self.fields}
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("Each changed record must be an object")
            line, supplied = change.get("line"), change.get("values")
            if type(line) is not int or line not in rows:
                raise ValueError("A changed record does not belong to this CSV")
            if not isinstance(supplied, dict):
                raise ValueError("Changed values must be an object")
            row = rows[line]
            for key, value in supplied.items():
                field = fields.get(key)
                if not field or not field["editable"]:
                    raise ValueError(f"{key} is not an editable field")
                row["raw"][key] = self._serialize(value, field, row["raw"][key])
            if supplied:
                self.lines[line] = _encode_row([row["raw"][column] for column in self.columns] + row["suffix"])

    @staticmethod
    def _serialize(value: Any, field: dict[str, Any], previous: str) -> str:
        kind = field["kind"]
        if kind == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{field['key']} must be true or false")
            return ("true" if value else "false") if previous.strip().casefold() in {"true", "false"} else ("1" if value else "0")
        if kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{field['key']} must be a whole number")
            if not field["min"] <= value <= field["max"]:
                raise ValueError(f"{field['key']} must be from {field['min']} through {field['max']}")
            return str(value)
        if kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{field['key']} must be a finite number")
            return format(value, ".15g")
        if kind == "text":
            if not isinstance(value, str) or "\n" in value or "\r" in value:
                raise ValueError(f"{field['key']} must be one line of text")
            return value
        raise ValueError(f"{field['key']} is not editable")

    def write_atomic(self, target: Path) -> str:
        target.parent.mkdir(parents=True, exist_ok=True)
        data = "".join(line + ending for line, ending in zip(self.lines, self.endings)).encode(self.encoding)
        fd, name = tempfile.mkstemp(prefix=target.name + ".", suffix=".lexeditor.tmp", dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(data); output.flush(); os.fsync(output.fileno())
            if _sha256(self.path) != self.sha256 or (target != self.path and target.exists()):
                raise RuntimeError("The FF9 CSV changed before saving. Reload it before saving.")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return _sha256(target)


class MemoriaDataStore:
    def __init__(self):
        self.baseline = ensure_baseline()
        self.project_data = paths.PROJECT_ROOT / "StreamingAssets" / "Data"
        self.baseline_roots = (paths.GAME_ROOT / "StreamingAssets" / "Data",
                               paths.DATA_ROOT / "StreamingAssets" / "Data",
                               paths.DATA_ROOT / "Data")

    def _paths(self, dataset: Dataset) -> tuple[Path, Path | None]:
        project = self.project_data / dataset.relative_path
        baseline = next((root / dataset.relative_path for root in self.baseline_roots
                         if (root / dataset.relative_path).is_file()), None)
        return project, baseline

    def status(self, dataset: Dataset) -> dict[str, Any]:
        project, baseline = self._paths(dataset)
        source = project if project.is_file() else baseline
        return {"key": dataset.key, "tab": dataset.tab, "label": dataset.label,
                "relativePath": "StreamingAssets/Data/" + dataset.relative_path.replace("\\", "/"),
                "controls": dataset.controls, "available": source is not None,
                "source": "project" if project.is_file() else "baseline" if baseline else None,
                "sourcePath": str(source) if source else None, "projectPath": str(project)}

    def load(self, key: str) -> dict[str, Any]:
        dataset = DATASET_BY_KEY.get(key)
        if not dataset:
            raise KeyError("Unknown FF9 dataset")
        status = self.status(dataset)
        if not status["available"]:
            raise FileNotFoundError(f"{status['relativePath']} is not present in the selected project or a Memoria/Hades data export")
        document = MemoriaCsvDocument(Path(status["sourcePath"]))
        return {**status, "sha256": document.sha256, "fields": document.fields,
                "rows": document.public_rows(dataset)}

    def save(self, key: str, expected_sha256: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
        dataset = DATASET_BY_KEY.get(key)
        if not dataset:
            raise KeyError("Unknown FF9 dataset")
        status = self.status(dataset)
        if not status["available"]:
            raise FileNotFoundError("The selected dataset has no proved Memoria CSV source")
        if not isinstance(changes, list):
            raise ValueError("Changes must be a list")
        source = Path(status["sourcePath"])
        document = MemoriaCsvDocument(source)
        if document.sha256 != expected_sha256:
            raise RuntimeError("The FF9 CSV changed outside Lexeditor. Reload it before saving.")
        before = document.lines.copy()
        document.apply(changes)
        if document.lines == before:
            return self.load(key)
        target = self.project_data / dataset.relative_path
        if source != target and target.exists():
            raise RuntimeError("The FF9 project CSV appeared after this dataset loaded. Reload it before saving.")
        resolved = target.resolve()
        if any(root.resolve() in resolved.parents for root in self.baseline_roots):
            raise RuntimeError("Select a mod project separate from the installed or cached baseline before saving")
        document.write_atomic(target)
        return self.load(key)


def catalog() -> list[dict[str, Any]]:
    store = MemoriaDataStore()
    return [store.status(dataset) for dataset in DATASETS]
