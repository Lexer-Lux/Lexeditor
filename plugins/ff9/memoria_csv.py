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
    # Column names that read better under this dataset's own meaning of the
    # column than under the generic humanized form. Items.csv stores the shop
    # purchase column as "Price" and the resale column as "SellingPrice"; the
    # same words mean something else in other tables, so the rename stays with
    # the dataset that means it.
    field_labels: tuple[tuple[str, str], ...] = ()
    # Columns whose real range, or whose documented values, are narrower than
    # their stored type. A card value is stored as a byte but QuadMist only
    # draws 1 through 9 and A for 10; the card's icon is stored as text but the
    # format documents every value it accepts.
    field_bounds: tuple[tuple[str, int, int], ...] = ()
    field_choices: tuple[tuple[str, tuple[str, ...]], ...] = ()


DATASETS = (
    Dataset("items", "items", "Items", "Items/Items.csv", "Item identity, prices, equipment classes, abilities, and usability"),
    Dataset("weapons", "weapons", "Weapons", "Items/Weapons.csv", "Weapon category, model, script, power, elements, rate, and sound"),
    Dataset("armor", "armor", "Armor", "Items/Armors.csv", "Physical and magical defence and evasion"),
    Dataset("item-effects", "items", "Item effects", "Items/ItemEffects.csv", "Targeting, script, power, rate, element, and status"),
    Dataset("abilities", "abilities", "Support abilities", "Characters/Abilities/AbilityGems.csv", "Support-ability gem costs and boosted versions"),
    Dataset("actions", "magic", "Battle actions", "Battle/Actions.csv", "Battle action targeting, animation, script, power, status, MP, and type"),
    Dataset("characters", "characters", "Character base stats", "Characters/BaseStats.csv", "Base dexterity, strength, magic, will, and gem capacity"),
    Dataset("character-parameters", "characters", "Character parameters", "Characters/CharacterParameters.csv", "Starting row, victory pose, category, command and equipment sets, model formula, and name keyword"),
    Dataset("default-equipment", "characters", "Starting equipment", "Characters/DefaultEquipment.csv", "Initial weapon, headgear, wristwear, armor, and accessory for each equipment set"),
    Dataset("leveling", "characters", "Level growth", "Characters/Leveling.csv", "Experience thresholds and HP/MP growth for levels 1 through 99"),
    Dataset("shops", "shops", "Shop inventories", "Items/ShopItems.csv", "Shop names, each stocked item with its buy and sell price, and the ordered item ids"),
    Dataset("synthesis", "synthesis", "Synthesis recipes", "Items/Synthesis.csv", "Recipe shops, price, result, and ingredients"),
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
    text = re.sub(r"^\d+\s*-\s*", "", text)
    return text.strip()


_FIELD_LABELS = {
    "SPSExtraPos": "SPS Extra Position",
    "SHPExtraPos": "SHP Extra Position",
    "ColorBase": "Glow Base Color",
}


def _field_label(column: str) -> str:
    if column in _FIELD_LABELS:
        return _FIELD_LABELS[column]
    value = column.replace("_", " ")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", value)
    value = re.sub(r"(?<=[A-Za-z0-9])\(", " (", value)
    return " ".join(value.split())


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
            columns = _parse_csv_line(line[1:].strip())
            type_line = self.lines[index + 1]
            if not type_line.startswith("#") or ";" not in type_line or type_line.startswith("#!"):
                continue
            types = _parse_csv_line(type_line[1:].strip())
            if len(columns) >= 2 and len(types) == len(columns):
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
            identity = by_name.get("Id", by_name.get("id", str(len(rows))))
            comment_name = by_name.get("Comment") or by_name.get("Name")
            suffix_name = _comment_text(suffix)
            name = comment_name or suffix_name
            if comment_name and suffix_name and re.fullmatch(r"Shop\s+\d+", comment_name.strip(), flags=re.I):
                richer = re.sub(r"^Shop\s+\d+\s*", "", suffix_name, flags=re.I).strip()
                if richer:
                    name = richer
            rows.append({"line": line_number, "id": identity,
                         "name": name or f"Record {identity}", "raw": by_name, "suffix": suffix})
        return rows

    def _describe_fields(self) -> list[dict[str, Any]]:
        result = []
        for column, declared in zip(self.columns, self.types):
            normalized = declared.strip().casefold()
            values = [row["raw"][column].strip() for row in self.rows]
            descriptor: dict[str, Any] = {
                "key": column, "label": _field_label(column),
                "declaredType": declared or "String",
                # Id is source identity and Comment is an upstream annotation,
                # not gameplay data. Neither should masquerade as a writable
                # property merely because it occupies a CSV cell.
                "editable": column.casefold() not in {"id", "comment"},
            }
            if normalized in _BOOLEAN_TYPES:
                descriptor["kind"] = "boolean"
            elif normalized in _INTEGER_RANGES:
                minimum, maximum = _INTEGER_RANGES[normalized]
                raw_values = [value for value in values if value]
                symbolic = any(not re.fullmatch(r"[-+]?\d+", value) for value in raw_values)
                if symbolic:
                    choices: list[str] = []
                    enum_like = True
                    for value in raw_values:
                        match = re.fullmatch(r".+\(\s*([-+]?\d+)\s*\)", value)
                        if not match or not minimum <= int(match.group(1)) <= maximum:
                            enum_like = False
                            break
                        if value not in choices:
                            choices.append(value)
                    if enum_like and choices:
                        descriptor.update(kind="enum", choices=choices, min=minimum, max=maximum)
                    else:
                        descriptor.update(kind="stored", editable=False)
                else:
                    descriptor.update(kind="integer", min=minimum, max=maximum)
            elif normalized in _FLOAT_TYPES:
                descriptor.update(kind="number", step="any")
            elif normalized == "vector3":
                descriptor.update(kind="fixed-list", length=3, itemKind="number", step="any", vector3=True)
            elif (fixed := re.fullmatch(r"(byte|uint8|sbyte|int8|uint16|int16|uint32|int32|uint64|int64)\[(\d+)\]", normalized)):
                length = int(fixed.group(2))
                item_type = fixed.group(1)
                if 1 <= length <= 32 and all(
                    not value or len([token for token in value.split(",") if token.strip()]) == length
                    for value in values
                ):
                    minimum, maximum = _INTEGER_RANGES[item_type]
                    descriptor.update(kind="fixed-list", length=length, itemKind="integer",
                                      itemMin=minimum, itemMax=maximum)
                else:
                    descriptor.update(kind="stored", editable=False)
            elif (fixed := re.fullmatch(r"(single|float|double)\[(\d+)\]", normalized)):
                length = int(fixed.group(2))
                if 1 <= length <= 32 and all(
                    not value or len([token for token in value.split(",") if token.strip()]) == length
                    for value in values
                ):
                    descriptor.update(kind="fixed-list", length=length, itemKind="number", step="any")
                else:
                    descriptor.update(kind="stored", editable=False)
            elif normalized.endswith("[]"):
                item_type = normalized[:-2].strip()
                descriptor.update(kind="list", itemType=item_type)
                if item_type in _INTEGER_RANGES:
                    descriptor.update(itemKind="integer", itemMin=_INTEGER_RANGES[item_type][0], itemMax=_INTEGER_RANGES[item_type][1])
                else:
                    descriptor.update(itemKind="token")
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
            "id": index + 1 if dataset.key == "leveling" else (int(row["id"]) if str(row["id"]).lstrip("-+").isdigit() else row["id"]),
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
        if kind == "fixed-list":
            tokens = [token.strip() for token in raw.split(",") if token.strip()]
            if field.get("vector3"):
                values = [float(token) for token in tokens]
                if any(not math.isfinite(value) for value in values):
                    raise ValueError(f"{field['key']} contains a non-finite number")
                if len(values) == 0:
                    return [0.0, 0.0, 0.0]
                if len(values) == 1:
                    return [values[0], 0.0, 0.0]
                if len(values) == 2:
                    return [values[0], 0.0, values[1]]
                return values[:3]
            if len(tokens) != field["length"]:
                raise ValueError(f"{field['key']} must contain exactly {field['length']} values")
            if field.get("itemKind") == "integer":
                return [int(token) for token in tokens]
            values = [float(token) for token in tokens]
            if any(not math.isfinite(value) for value in values):
                raise ValueError(f"{field['key']} contains a non-finite number")
            return values
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
        if kind == "enum":
            if not isinstance(value, str) or value not in field.get("choices", []):
                raise ValueError(f"{field['key']} must be one of its named values")
            return value
        if kind == "fixed-list":
            if not isinstance(value, list) or len(value) != field["length"]:
                raise ValueError(f"{field['key']} must contain exactly {field['length']} values")
            serialized: list[str] = []
            if field.get("itemKind") == "integer":
                minimum, maximum = field["itemMin"], field["itemMax"]
                for item in value:
                    if isinstance(item, bool) or not isinstance(item, int):
                        raise ValueError(f"{field['key']} must contain only whole numbers")
                    if not minimum <= item <= maximum:
                        raise ValueError(f"{field['key']} entries must be from {minimum} through {maximum}")
                    serialized.append(str(item))
            else:
                for item in value:
                    if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
                        raise ValueError(f"{field['key']} must contain only finite numbers")
                    serialized.append(format(item, ".15g"))
            return ", ".join(serialized)
        if kind == "list":
            if not isinstance(value, str) or "\n" in value or "\r" in value or ";" in value:
                raise ValueError(f"{field['key']} must be a comma-separated one-line list")
            tokens = [token.strip() for token in value.split(",") if token.strip()]
            if field.get("itemKind") == "integer":
                minimum, maximum = field["itemMin"], field["itemMax"]
                for token in tokens:
                    if not re.fullmatch(r"[-+]?\d+", token):
                        raise ValueError(f"{field['key']} must contain only whole numbers")
                    number = int(token)
                    if not minimum <= number <= maximum:
                        raise ValueError(f"{field['key']} entries must be from {minimum} through {maximum}")
            else:
                for token in tokens:
                    if not re.fullmatch(r"[A-Za-z0-9_.:+-]+", token):
                        raise ValueError(f"{field['key']} contains an invalid list token")
            return ", ".join(tokens)
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
        payload = {**status, "sha256": document.sha256,
                   "fields": self.labelled_fields(dataset, document.fields),
                   "rows": document.public_rows(dataset)}
        # What each record shipped with, so a property can be restored to the
        # game's own value after an edit. A project overlay is written as a copy
        # of its source with the reader's edits, so both documents share their
        # line numbers and the baseline can be read by line. When no overlay
        # exists the loaded values already are the shipped ones, and the reader
        # has nothing to compare against.
        project, baseline = self._paths(dataset)
        if project.is_file() and baseline is not None and baseline != project:
            vanilla = MemoriaCsvDocument(baseline).public_rows(dataset)
            payload["vanilla"] = {str(row["line"]): row["values"] for row in vanilla}
        return payload

    @staticmethod
    def labelled_fields(dataset: Dataset, fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The document's field descriptions under this dataset's own meaning."""
        overrides = dict(dataset.field_labels)
        bounds = {key: (minimum, maximum) for key, minimum, maximum in dataset.field_bounds}
        choices = dict(dataset.field_choices)
        if not overrides and not bounds and not choices:
            return fields
        result = []
        for field in fields:
            updated = {**field, "label": overrides.get(field["key"], field["label"])}
            if field["editable"] and field["key"] in bounds:
                minimum, maximum = bounds[field["key"]]
                updated.update(min=minimum, max=maximum)
            if field["editable"] and field["key"] in choices:
                updated.update(kind="enum", choices=list(choices[field["key"]]))
            result.append(updated)
        return result

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
