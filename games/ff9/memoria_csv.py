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


DATASETS = (
    Dataset('items', 'items', 'Items', 'Items/Items.csv', 'Item identity, prices, equipment classes, abilities, and usability'),
    Dataset('weapons', 'weapons', 'Weapons', 'Items/Weapons.csv', 'Weapon category, model, script, power, elements, rate, and sound'),
    Dataset('armor', 'armor', 'Armor', 'Items/Armors.csv', 'Physical and magical defence and evasion'),
    Dataset('item-effects', 'items', 'Item effects', 'Items/ItemEffects.csv', 'Targeting, script, power, rate, element, and status'),
    Dataset('initial-items', 'items', 'Initial inventory', 'Items/InitialItems.csv', 'Starting item IDs and quantities'),
    Dataset('mix-items', 'synthesis', 'Mix recipes', 'Items/MixItems.csv', 'Mix recipe results and ingredients'),
    Dataset('item-stats', 'items', 'Equipment stats', 'Items/Stats.csv', 'Equipment stat bonuses and elemental properties'),
    Dataset('shops', 'shops', 'Shop inventories', 'Items/ShopItems.csv', 'Shop IDs and ordered item inventories'),
    Dataset('synthesis', 'synthesis', 'Synthesis recipes', 'Items/Synthesis.csv', 'Recipe shops, price, result, and ingredients'),
    Dataset('abilities', 'abilities', 'Support abilities', 'Characters/Abilities/AbilityGems.csv', 'Support-ability gem costs and boosted versions'),
    Dataset('ability-zidane', 'abilities', 'Zidane abilities', 'Characters/Abilities/Zidane.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-vivi', 'abilities', 'Vivi abilities', 'Characters/Abilities/Vivi.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-garnet', 'abilities', 'Garnet abilities', 'Characters/Abilities/Garnet.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-steiner', 'abilities', 'Steiner abilities', 'Characters/Abilities/Steiner.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-freya', 'abilities', 'Freya abilities', 'Characters/Abilities/Freya.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-quina', 'abilities', 'Quina abilities', 'Characters/Abilities/Quina.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-eiko', 'abilities', 'Eiko abilities', 'Characters/Abilities/Eiko.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-amarant', 'abilities', 'Amarant abilities', 'Characters/Abilities/Amarant.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-beatrix-1', 'abilities', 'Beatrix abilities 1', 'Characters/Abilities/Beatrix1.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-beatrix-2', 'abilities', 'Beatrix abilities 2', 'Characters/Abilities/Beatrix2.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-blank-1', 'abilities', 'Blank abilities 1', 'Characters/Abilities/Blank1.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-blank-2', 'abilities', 'Blank abilities 2', 'Characters/Abilities/Blank2.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-cinna-1', 'abilities', 'Cinna abilities 1', 'Characters/Abilities/Cinna1.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-cinna-2', 'abilities', 'Cinna abilities 2', 'Characters/Abilities/Cinna2.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-marcus-1', 'abilities', 'Marcus abilities 1', 'Characters/Abilities/Marcus1.csv', 'Ability IDs and AP requirements'),
    Dataset('ability-marcus-2', 'abilities', 'Marcus abilities 2', 'Characters/Abilities/Marcus2.csv', 'Ability IDs and AP requirements'),
    Dataset('characters', 'characters', 'Character base stats', 'Characters/BaseStats.csv', 'Base dexterity, strength, magic, will, and gem capacity'),
    Dataset('battle-parameters', 'characters', 'Battle parameters', 'Characters/BattleParameters.csv', 'Models, animations, battle geometry, status anchors, and weapon sounds'),
    Dataset('character-parameters', 'characters', 'Character parameters', 'Characters/CharacterParameters.csv', 'Starting row, victory pose, category, command and equipment sets, model formula, and name keyword'),
    Dataset('command-sets', 'characters', 'Command sets', 'Characters/CommandSets.csv', 'Per-character command set assignments'),
    Dataset('commands', 'characters', 'Commands', 'Characters/Commands.csv', 'Battle command types and ability lists'),
    Dataset('default-equipment', 'characters', 'Starting equipment', 'Characters/DefaultEquipment.csv', 'Initial weapon, headgear, wristwear, armor, and accessory for each equipment set'),
    Dataset('leveling', 'characters', 'Level growth', 'Characters/Leveling.csv', 'Experience thresholds and HP/MP growth for levels 1 through 99'),
    Dataset('actions', 'magic', 'Battle actions', 'Battle/Actions.csv', 'Battle action targeting, animation, script, power, status, MP, and type'),
    Dataset('magic-sword-sets', 'magic', 'Magic Sword sets', 'Battle/MagicSwordSets.csv', 'Supporter, beneficiary, and ability set mapping'),
    Dataset('status-data', 'magic', 'Status data', 'Battle/StatusData.csv', 'Status priority, timing, colors, and tick behavior'),
    Dataset('status-sets', 'magic', 'Status sets', 'Battle/StatusSets.csv', 'Named status-set membership'),
    Dataset('sfx-shp', 'effects', 'SHP definitions', 'SpecialEffects/Common/SHP.csv', 'Shape-particle definitions and textures'),
    Dataset('sfx-sps', 'effects', 'SPS definitions', 'SpecialEffects/Common/SPS.csv', 'Sprite-particle definitions, textures, colors, and timing'),
    Dataset('tetra-cards', 'tetra-master', 'Tetra Master cards', 'TetraMaster/TripleTriad.csv', 'Card attack, defence, type, and arrow data'),
    Dataset('world-transport', 'world', 'Transport controls', 'World/TransportControls.csv', 'World transport movement and collision parameters'),
    Dataset('world-weather', 'world', 'Weather colors', 'World/WeatherColors.csv', 'World light, fog, and ambient weather colors'),
)
DATASET_BY_KEY = {value.key: value for value in DATASETS}

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


def _parse_csv_line(value: str) -> list[str]:
    return next(csv.reader([value], delimiter=";", quotechar='"'))


def _write_csv_line(values: list[str]) -> str:
    output = io.StringIO(newline="")
    csv.writer(output, delimiter=";", quotechar='"', lineterminator="").writerow(values)
    return output.getvalue()


def _comment_text(suffix: list[str]) -> str:
    text = " ".join(value for value in suffix if value).strip()
    text = re.sub(r"^#\s*", "", text)
    text = re.sub(r"^\du+\s*-\s*", "", text)
    return text.strip()


class MemoriaCsvDocument:
    def __init__(self, path: Path):
        self.path = path
        raw = path.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        if raw.startswith(b"\xef\xbb\xbf"):
            self.encoding = "utf-8-sig"
            text = raw.decode(self.encoding)
        else:
            try:
                self.encoding = "utf-8"
                text = raw.decode(self.encoding)
            except UnicodeDecodeError:
                # Preserve the pinned data's Windows-1252 punctuation.
                self.encoding = "cp1252"
                text = raw.decode(self.encoding)
        self.newline = "\r\n" if "\r\n" in text else "\n"
        # Keep each original terminator, including a missing final newline.
        self.lines = text.splitlines()
        self.endings = [line[len(line.rstrip("\r\n")):] for line in text.splitlines(keepends=True)]
        self.columns, self.types = self._find_schema()
        self.rows = self._read_rows()
        self.fields = self._describe_fields()

    def _find_schema(self) -> tuple[list[str], list[str]]:
        for index, line in enumerate(self.lines[:-1]):
            if not line.startswith("#") or ";" not in line or line.startswith("#!"):
                continue
            columns = [value.strip() for value in _parse_csv_line(line[1:].strip())]
            type_line = self.lines[index + 1]
            if not type_line.startswith("#") or ";" not in type_line or type_line.startswith("#!"):
                continue
            types = [value.strip() for value in _parse_csv_line(type_line[1:].strip())]
            # Some Memoria schemas describe optional trailing structures whose
            # type expressions themselves contain semicolons (BattleParameters).
            # The active #! directives determine how many fields each row actually
            # stores, so trim the schema to the first concrete record rather than
            # guessing the optional layout.
            data_count = 0
            for candidate in self.lines[index + 2:]:
                if not candidate or candidate.lstrip().startswith("#"):
                    continue
                values = _parse_csv_line(candidate)
                data_count = next((i for i, value in enumerate(values)
                                   if value.lstrip().startswith("#")), len(values))
                break
            if data_count and data_count <= len(columns) and data_count <= len(types):
                columns = columns[:data_count]
                types = types[:data_count]
            while columns and not columns[-1]:
                columns.pop()
                if len(types) > len(columns):
                    types = types[:len(columns)]
            if len(columns) >= 2 and len(types) >= len(columns):
                types = types[:len(columns)]
                if len(set(columns)) != len(columns) or any(not name for name in columns):
                    raise ValueError(f"Memoria CSV has duplicate or empty column names: {self.path}")
                return columns, types
        raise ValueError(f"Memoria CSV schema header was not found: {self.path}")

    def _read_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(self.lines):
            if not line or line.lstrip().startswith("#"):
                continue
            values = _parse_csv_line(line)
            if len(values) < len(self.columns):
                raise ValueError(f"Line {line_number + 1} has fewer fields than its schema: {self.path}")
            data = values[:len(self.columns)]
            suffix = values[len(self.columns):]
            by_name = dict(zip(self.columns, data))
            identity = by_name.get("Id", by_name.get("id", str(len(rows)))
            name = by_name.get("Comment") or by_name.get("Name") or _comment_text(suffix)
            rows.append({"line": line_number, "id": identity,
                         "name": name or f"Record {identity}", "raw": by_name, "suffix": suffix})
        return rows

    def _describe_fields(self) -> list[dict[str, Any]]:
        result = []
        for column, declared in zip(self.columns, self.types):
            normalized = declared.strip().casefold()
            values = [row["raw"][column].strip() for row in self.rows]
            descriptor: dict[str, Any] = {
                "key": column, "label": column.replace("_", " "),
                "declaredType": declared or "String", "editable": column.casefold() != "id",
            }
            if normalized in _BOOLEAN_TYPES:
                descriptor["kind"] = "boolean"
            elif normalized in _INTEGER_RANGES:
                symbolic = any(value and not re.fullmatch(r"[-+]?\d+", value) for value in values)
                if symbolic:
                    descriptor.update(kind="stored", editable=False)
                else:
                    descriptor.update(kind="integer", min=_INTEGER_RANGES[normalized][0], max=_INTEGER_RANGES[normalized][1])
            elif normalized in _FLOAT_TYPES:
                descriptor.update(kind="number", step="any")
            elif "[" in normalized or "{" in normalized:
                descriptor.update(kind="stored", editable=False)
            elif normalized in {"string", ""}:
                descriptor["kind"] = "text"
            else:
                descriptor.update(kind="stored", editable=False)
            result.append(descriptor)
        return result

    def public_rows(self, dataset: Dataset) -> list[dict[str, Any]]:
        rows = self.rows
        if dataset.filter_column:
            rows = [row for row in rows if row["raw"].get(dataset.filter_column) == dataset.filter_value]
        fields = {field["key"]: field for field in self.fields}
        return [{
            "line": row["line"],
            "id": (index + 1 if not any(key.casefold() == "id" for key in row["raw"])
                   else (int(row["id"]) if str(row["id"]).lstrip("-+").isdigit() else row["id"])),
            "name": row["name"],
            "values": {key: self._public_value(value, fields[key]) for key, value in row["raw"].items()},
        } for index, row in enumerate(rows)]

    @staticmethod
    def _public_value(raw: str, field: dict[str, Any]) -> Any:
        kind = field["kind"]
        if kind == "boolean":
            return raw.strip().casefold() in {"1", "true"}
        if kind == "integer" and raw.strip():
            return int(raw)
        if kind == "number" and raw.strip():
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError(f"{field['key']} contains a non-finite number")
            return value
        return raw

    def apply(self, changes: list[dict[str, Any]]) -> None:
        row_by_line = {row["line"]: row for row in self.rows}
        field_by_key = {field["key"]: field for field in self.fields}
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError("Each changed record must be an object")
            line = change.get("line")
            if type(line) is not int or line not in row_by_line:
                raise ValueError("A changed record does not belong to this CSV")
            row = row_by_line[line]
            supplied = change.get("values")
            if not isinstance(supplied, dict):
                raise ValueError("Changed values must be an object")
            if not supplied:
                continue
            for key, value in supplied.items():
                field = field_by_key.get(key)
                if not field or not field["editable"]:
                    raise ValueError(f"{key} is not an editable field")
                row["raw"][key] = self._serialize(value, field, row["raw"][key])
            data = [row["raw"][column] for column in self.columns] + row["suffix"]
            self.lines[line] = _write_csv_line(data)

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
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
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
        self.baseline_roots = (
            paths.GAME_ROOT / "StreamingAssets" / "Data",
            paths.DATA_ROOT / "StreamingAssets" / "Data",
            paths.DATA_ROOT / "Data",
        )

    def _paths(self, dataset: Dataset) -> tuple[Path, Path | None]:
        project = self.project_data / dataset.relative_path
        baseline = next((root / dataset.relative_path for root in self.baseline_roots if (root / dataset.relative_path).is_file()), None)
        return project, baseline

    def status(self, dataset: Dataset) -> dict[str, Any]:
        project, baseline = self._paths(dataset)
        source = project if project.is_file() else baseline
        return {
            "key": dataset.key, "tab": dataset.tab, "label": dataset.label,
            "relativePath": "StreamingAssets/Data/" + dataset.relative_path.replace("\\", "/"),
            "controls": dataset.controls, "available": source is not None,
            "source": "project" if project.is_file() else "baseline" if baseline else None,
            "sourcePath": str(source) if source else None, "projectPath": str(project),
        }

    def load(self, key: str) -> dict[str, Any]:
        dataset = DATASET_BY_KEY.get(key)
        if not dataset:
            raise KeyError("Unknown FF9 dataset")
        status = self.status(dataset)
        if not status["available"]:
            raise FileNotFoundError(f"{status['relativePath']} is not present in the selected project or a Memoria/Hades data export")
        document = MemoriaCsvDocument(Path(status["sourcePath"]))
        return {**status, "sha256": document.sha256, "fields": document.fields, "rows": document.public_rows(dataset)}

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
        original_lines = document.lines.copy()
        document.apply(changes)
        if document.lines == original_lines:
            return self.load(key)
        target = self.project_data / dataset.relative_path
        if source != target and target.exists():
            raise RuntimeError("The FF9 project CSV appeared after this dataset loaded. Reload it before saving.")
        resolved_target = target.resolve()
        if any(root.resolve() in resolved_target.parents for root in self.baseline_roots):
            raise RuntimeError("Select a mod project separate from the installed or cached baseline before saving")
        document.write_atomic(target)
        return self.load(key)


def catalog() -> list[dict[str, Any]]:
    store = MemoriaDataStore()
    return [store.status(dataset) for dataset in DATASETS]
