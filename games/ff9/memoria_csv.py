"""Safe reader and project-overlay writer for Memoria's FF9 CSV formats."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
import re
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
    Dataset("items", "items", "Items", "Items/Items.csv", "Item identity, prices, equipment classes, abilities, and usability"),
    Dataset("weapons", "weapons", "Weapons", "Items/Weapons.csv", "Weapon category, model, script, power, elements, rate, and sound"),
    Dataset("armor", "armor", "Armor", "Items/Armors.csv", "Physical and magical defence and evasion"),
    Dataset("item-effects", "items", "Item effects", "Items/ItemEffects.csv", "Targeting, script, power, rate, element, and status"),
    Dataset("abilities", "abilities", "Support abilities", "Characters/Abilities/AbilityGems.csv", "Support-ability gem costs and boosted versions"),
    Dataset("actions", "magic", "Battle actions", "Battle/Actions.csv", "Battle action targeting, animation, script, power, status, MP, and type"),
    Dataset("characters", "characters", "Character base stats", "Characters/BaseStats.csv", "Base dexterity, strength, magic, will, and gem capacity"),
    Dataset("shops", "shops", "Shop inventories", "Items/ShopItems.csv", "Shop IDs and ordered item inventories"),
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
                # Memoria's pinned vanilla data includes Windows-1252 punctuation.
                # Preserve that encoding when Lexeditor writes the project overlay.
                self.encoding = "cp1252"
                text = raw.decode(self.encoding)
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.lines = text.splitlines()
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
            name = by_name.get("Comment") or by_name.get("Name") or _comment_text(suffix)
            rows.append({
                "line": line_number,
                "id": identity,
                "name": name or f"Record {identity}",
                "raw": by_name,
                "suffix": suffix,
            })
        return rows

    def _describe_fields(self) -> list[dict[str, Any]]:
        result = []
        for column, declared in zip(self.columns, self.types):
            normalized = declared.strip().casefold()
            values = [row["raw"][column].strip() for row in self.rows]
            descriptor: dict[str, Any] = {
                "key": column,
                "label": column.replace("_", " "),
                "declaredType": declared or "String",
                "editable": column.casefold() != "id",
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
            "id": int(row["id"]) if str(row["id"]).lstrip("-+").isdigit() else row["id"],
            "name": row["name"],
            "values": {key: self._public_value(value, fields[key]) for key, value in row["raw"].items()},
        } for row in rows]

    @staticmethod
    def _public_value(raw: str, field: dict[str, Any]) -> Any:
        kind = field["kind"]
        if kind == "boolean":
            return raw.strip().casefold() in {"1", "true"}
        if kind == "integer" and raw.strip():
            return int(raw)
        if kind == "number" and raw.strip():
            return float(raw)
        return raw

    def apply(self, changes: list[dict[str, Any]]) -> None:
        row_by_line = {row["line"]: row for row in self.rows}
        field_by_key = {field["key"]: field for field in self.fields}
        for change in changes:
            line = change.get("line")
            if not isinstance(line, int) or line not in row_by_line:
                raise ValueError("A changed record does not belong to this CSV")
            row = row_by_line[line]
            supplied = change.get("values")
            if not isinstance(supplied, dict):
                raise ValueError("Changed values must be an object")
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
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{field['key']} must be a number")
            return format(value, ".15g")
        if kind == "text":
            if not isinstance(value, str) or "\n" in value or "\r" in value:
                raise ValueError(f"{field['key']} must be one line of text")
            return value
        raise ValueError(f"{field['key']} is not editable")

    def write_atomic(self, target: Path) -> str:
        target.parent.mkdir(parents=True, exist_ok=True)
        data = (self.newline.join(self.lines) + self.newline).encode(self.encoding)
        temporary = target.with_name(target.name + ".lexeditor.tmp")
        temporary.write_bytes(data)
        os.replace(temporary, target)
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
            "controls": dataset.controls,
            "available": source is not None,
            "source": "project" if project.is_file() else "baseline" if baseline else None,
            "sourcePath": str(source) if source else None,
            "projectPath": str(project),
        }

    def load(self, key: str) -> dict[str, Any]:
        dataset = DATASET_BY_KEY.get(key)
        if not dataset:
            raise KeyError("Unknown FF9 dataset")
        status = self.status(dataset)
        if not status["available"]:
            raise FileNotFoundError(
                f"{status['relativePath']} is not present in the selected project or a Memoria/Hades data export"
            )
        document = MemoriaCsvDocument(Path(status["sourcePath"]))
        return {
            **status,
            "sha256": document.sha256,
            "fields": document.fields,
            "rows": document.public_rows(dataset),
        }

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
        if _sha256(source) != expected_sha256:
            raise RuntimeError("The FF9 CSV changed outside Lexeditor. Reload it before saving.")
        document = MemoriaCsvDocument(source)
        document.apply(changes)
        target = self.project_data / dataset.relative_path
        if source != target and target.exists():
            raise RuntimeError("The FF9 project CSV appeared after this dataset loaded. Reload it before saving.")
        document.write_atomic(target)
        return self.load(key)


def catalog() -> list[dict[str, Any]]:
    store = MemoriaDataStore()
    return [store.status(dataset) for dataset in DATASETS]
