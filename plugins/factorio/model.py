"""Safe Factorio 2.1 prototype editing and deterministic override-mod export.

Lexeditor never evaluates a source mod's Lua.  The immutable source boundary is
Factorio's own JSON prototype dump (created with --dump-data) plus, optionally,
the game's mod-list.json.  Edits live in overrides.json and export as a separate
late prototype-stage mod.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile
import zipfile
from typing import Any


SUPPORTED_FACTORIO = (2, 1)
PROJECT_FILE = "factorio-project.json"
OVERRIDES_FILE = "overrides.json"
SOURCE_DIR = "source"
SOURCE_DUMP = "data-raw-dump.json"
SOURCE_MOD_LIST = "mod-list.json"
FORMAT_VERSION = 1
UINT32_MAX = 4_294_967_295
UINT64_MAX = 18_446_744_073_709_551_615

# Concrete 2.1 prototypes documented as descendants of ItemPrototype.  Editing
# is deliberately limited to the inherited stack_size field; other properties
# remain visible source data until they have their own semantic editor.
ITEM_TYPES = frozenset({
    "ammo", "armor", "blueprint", "blueprint-book", "capsule",
    "copy-paste-tool", "deconstruction-item", "gun", "item",
    "item-with-entity-data", "item-with-inventory", "item-with-label",
    "item-with-tags", "module", "rail-planner", "repair-tool",
    "selection-tool", "space-platform-starter-pack", "spidertron-remote",
    "tool", "upgrade-item",
})
FIXED_STACK_ONE_TYPES = frozenset({
    "blueprint", "blueprint-book", "copy-paste-tool", "deconstruction-item",
    "item-with-inventory", "selection-tool", "spidertron-remote", "upgrade-item",
})
MACHINE_TYPES = frozenset({"assembling-machine", "furnace", "rocket-silo"})
KINDS = ("recipes", "items", "machines", "technologies")
SAFE_MOD_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
DEPENDENCY_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
VERSION_TEXT = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
DEPENDENCY_TEXT = re.compile(
    r"^\s*(?:(?:\(\?\)|[!?+~])\s*)?"
    r"(?P<name>[A-Za-z0-9_-]+)"
    r"(?:\s*(?:<=|>=|=|<|>)\s*(?P<version>\d+\.\d+\.\d+))?\s*$"
)


class FactorioDataError(ValueError):
    """A user-actionable source, schema, range, or reference error."""


@dataclass(frozen=True)
class InstallInfo:
    root: str
    version: str
    supported: bool
    space_age_installed: bool
    quality_installed: bool
    elevated_rails_installed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "version": self.version,
            "supported": self.supported,
            "dlc": {
                "spaceAge": self.space_age_installed,
                "quality": self.quality_installed,
                "elevatedRails": self.elevated_rails_installed,
            },
        }


def _read_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FactorioDataError(f"Missing {label}: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise FactorioDataError(f"Invalid {label}: {path}: {error}") from error


def _version_pair(version: str) -> tuple[int, int] | None:
    match = re.match(r"^(\d+)\.(\d+)(?:\.|$)", str(version).strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def _bounded_mod_version(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise FactorioDataError(f"{label} must use number.number.number")
    match = VERSION_TEXT.fullmatch(value.strip())
    if not match:
        raise FactorioDataError(f"{label} must use number.number.number")
    parts = tuple(int(match.group(key)) for key in ("major", "minor", "patch"))
    if any(part > 65535 for part in parts):
        raise FactorioDataError(f"{label} components must be between 0 and 65535")
    return value.strip()


def detect_install(root: Path) -> InstallInfo:
    """Read trusted JSON shipped with Factorio; no game/mod code is executed."""
    root = Path(root).expanduser().resolve()
    base = _read_json(root / "data" / "base" / "info.json", label="Factorio base info")
    if not isinstance(base, dict) or not isinstance(base.get("version"), str):
        raise FactorioDataError("Factorio data/base/info.json has no version")
    version = base["version"].strip()
    pair = _version_pair(version)
    return InstallInfo(
        root=str(root),
        version=version,
        supported=pair == SUPPORTED_FACTORIO,
        space_age_installed=(root / "data" / "space-age" / "info.json").is_file(),
        quality_installed=(root / "data" / "quality" / "info.json").is_file(),
        elevated_rails_installed=(root / "data" / "elevated-rails" / "info.json").is_file(),
    )


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FactorioDataError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    # Factorio's JSON dump has historically represented a few empty arrays as
    # empty objects.  Accept that one known serialization quirk, but never
    # reinterpret a non-empty object as an array.
    if value == {}:
        return []
    if not isinstance(value, list):
        raise FactorioDataError(f"{label} must be an array")
    return value


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FactorioDataError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise FactorioDataError(f"{label} must be finite")
    return result


def _positive_number(value: Any, label: str, *, minimum: float = 0.0) -> float:
    result = _finite_number(value, label)
    if not result > minimum:
        comparator = f"> {minimum:g}" if minimum else "> 0"
        raise FactorioDataError(f"{label} must be {comparator}")
    return result


def _uint(value: Any, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FactorioDataError(f"{label} must be an integer")
    if not 0 <= value <= maximum:
        raise FactorioDataError(f"{label} must be between 0 and {maximum}")
    return value


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise FactorioDataError(f"{label} must be true or false")
    return value


def _names(value: Any, label: str) -> list[str]:
    result = []
    for index, entry in enumerate(_array(value, label)):
        if not isinstance(entry, str) or not entry:
            raise FactorioDataError(f"{label}[{index}] must be a non-empty prototype name")
        result.append(entry)
    if len(result) != len(set(result)):
        raise FactorioDataError(f"{label} contains a duplicate reference")
    return result


def _raw_root(payload: Any) -> dict[str, Any]:
    payload = _mapping(payload, "Factorio prototype dump")
    if isinstance(payload.get("data"), dict) and isinstance(payload["data"].get("raw"), dict):
        payload = payload["data"]["raw"]
    elif isinstance(payload.get("raw"), dict) and len(payload) == 1:
        payload = payload["raw"]
    if not payload or not all(isinstance(key, str) and isinstance(value, dict)
                              for key, value in payload.items()):
        raise FactorioDataError(
            "Prototype dump must contain Factorio data.raw as prototype-type objects"
        )
    return payload


class PrototypeStore:
    """Read one Factorio data.raw dump and apply only modeled overrides."""

    def __init__(self, raw: dict[str, Any], overrides: dict[str, Any] | None = None):
        self.raw = _raw_root(raw)
        self.overrides = validate_overrides(overrides or {"format": FORMAT_VERSION, "edits": {}})
        self._indexes = self._build_indexes()
        self._validate_override_targets()

    @classmethod
    def from_dump(cls, dump: Path) -> "PrototypeStore":
        """The game's own prototypes with no overrides: vanilla, no mod open."""
        raw = _read_json(Path(dump), label="Factorio prototype dump")
        return cls(raw, {"format": FORMAT_VERSION, "edits": {}})

    @classmethod
    def from_project(cls, project: Path) -> "PrototypeStore":
        project = Path(project).expanduser().resolve()
        raw = _read_json(project / SOURCE_DIR / SOURCE_DUMP, label="Factorio prototype dump")
        override_path = project / OVERRIDES_FILE
        overrides = (_read_json(override_path, label="Factorio overrides")
                     if override_path.exists()
                     else {"format": FORMAT_VERSION, "edits": {}})
        return cls(raw, overrides)

    def _bucket(self, prototype_type: str) -> dict[str, Any]:
        bucket = self.raw.get(prototype_type, {})
        return bucket if isinstance(bucket, dict) else {}

    def _build_indexes(self) -> dict[str, Any]:
        items: dict[str, tuple[str, dict[str, Any]]] = {}
        for prototype_type in sorted(ITEM_TYPES):
            for name, record in self._bucket(prototype_type).items():
                if isinstance(record, dict) and "stack_size" in record:
                    items[name] = (prototype_type, record)
        machines: dict[str, tuple[str, dict[str, Any]]] = {}
        for prototype_type in sorted(MACHINE_TYPES):
            for name, record in self._bucket(prototype_type).items():
                if isinstance(record, dict):
                    machines[name] = (prototype_type, record)
        return {
            "recipes": self._bucket("recipe"),
            "items": items,
            "machines": machines,
            "technologies": self._bucket("technology"),
            "fluids": self._bucket("fluid"),
            "recipeCategories": self._bucket("recipe-category"),
        }

    def names(self, kind: str) -> set[str]:
        if kind not in KINDS:
            raise FactorioDataError(f"Unknown Factorio dataset: {kind}")
        return set(self._indexes[kind])

    def _source(self, kind: str, name: str) -> tuple[str, dict[str, Any]]:
        if kind == "items" or kind == "machines":
            entry = self._indexes[kind].get(name)
            if entry is None:
                raise FactorioDataError(f"Unknown {kind[:-1]} prototype: {name}")
            return entry
        record = self._indexes[kind].get(name)
        if not isinstance(record, dict):
            raise FactorioDataError(f"Unknown {kind[:-1]} prototype: {name}")
        return ("recipe" if kind == "recipes" else "technology"), record

    def _validate_override_targets(self) -> None:
        for kind, records in self.overrides["edits"].items():
            if kind not in KINDS:
                raise FactorioDataError(f"Unsupported override dataset: {kind}")
            for name, changes in records.items():
                self.validate_edit(kind, name, changes)

    def _technology_prerequisites(self, name: str, candidate: list[str] | None = None) -> list[str]:
        if candidate is not None:
            return candidate
        patch = self.overrides["edits"].get("technologies", {}).get(name, {})
        if "prerequisites" in patch:
            return list(patch["prerequisites"])
        source = self._indexes["technologies"].get(name, {})
        value = source.get("prerequisites", []) if isinstance(source, dict) else []
        return list(value) if isinstance(value, list) else []

    def _prerequisite_cycle(self, name: str, candidate: list[str]) -> bool:
        visited: set[str] = set()
        active: set[str] = set()

        def walk(current: str) -> bool:
            if current in active:
                return current == name
            if current in visited:
                return False
            visited.add(current)
            active.add(current)
            prerequisites = (
                candidate if current == name
                else self._technology_prerequisites(current)
            )
            for prerequisite in prerequisites:
                if prerequisite == name or walk(prerequisite):
                    return True
            active.remove(current)
            return False

        return walk(name)

    def diagnostics(self) -> list[dict[str, str]]:
        """Report reference problems in modeled source fields without rewriting them."""
        problems: list[dict[str, str]] = []
        item_or_fluid = set(self._indexes["items"]) | set(self._indexes["fluids"])
        recipes = set(self._indexes["recipes"])
        techs = set(self._indexes["technologies"])
        categories = set(self._indexes["recipeCategories"])
        for name, record in self._indexes["recipes"].items():
            if not isinstance(record, dict):
                continue
            for field in ("ingredients", "results"):
                value = record.get(field, [])
                try:
                    entries = _array(value, f"recipe {name} {field}")
                except FactorioDataError as error:
                    problems.append({"severity": "error", "record": f"recipe:{name}",
                                     "message": str(error)})
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    ref = entry.get("name")
                    if isinstance(ref, str) and ref not in item_or_fluid:
                        problems.append({"severity": "warning", "record": f"recipe:{name}",
                                         "message": f"{field} references missing item/fluid {ref}"})
            for category in record.get("categories", []) if isinstance(record.get("categories"), list) else []:
                if category not in categories:
                    problems.append({"severity": "warning", "record": f"recipe:{name}",
                                     "message": f"references missing recipe category {category}"})
        for name, (_ptype, record) in self._indexes["machines"].items():
            for category in record.get("crafting_categories", []) if isinstance(record.get("crafting_categories"), list) else []:
                if category not in categories:
                    problems.append({"severity": "warning", "record": f"machine:{name}",
                                     "message": f"references missing recipe category {category}"})
        for name, record in self._indexes["technologies"].items():
            if not isinstance(record, dict):
                continue
            for prerequisite in record.get("prerequisites", []) if isinstance(record.get("prerequisites"), list) else []:
                if prerequisite not in techs:
                    problems.append({"severity": "warning", "record": f"technology:{name}",
                                     "message": f"references missing technology {prerequisite}"})
            for effect in record.get("effects", []) if isinstance(record.get("effects"), list) else []:
                if isinstance(effect, dict) and effect.get("type") == "unlock-recipe":
                    recipe = effect.get("recipe")
                    if isinstance(recipe, str) and recipe not in recipes:
                        problems.append({"severity": "warning", "record": f"technology:{name}",
                                         "message": f"unlocks missing recipe {recipe}"})
        return problems

    def rows(self, kind: str) -> list[dict[str, Any]]:
        if kind not in KINDS:
            raise FactorioDataError(f"Unknown Factorio dataset: {kind}")
        rows = []
        for name in sorted(self._indexes[kind], key=str.casefold):
            prototype_type, source = self._source(kind, name)
            patch = self.overrides["edits"].get(kind, {}).get(name, {})
            merged = dict(source)
            if kind == "technologies":
                unit = dict(source.get("unit") or {})
                if "unit_count" in patch:
                    unit["count"] = patch["unit_count"]
                if "unit_time" in patch:
                    unit["time"] = patch["unit_time"]
                merged["unit"] = unit
                for key in ("enabled", "prerequisites"):
                    if key in patch:
                        merged[key] = patch[key]
            else:
                merged.update(patch)
            row: dict[str, Any] = {
                "id": f"{prototype_type}:{name}",
                "name": name,
                "prototypeType": prototype_type,
                "modified": bool(patch),
            }
            if kind == "recipes":
                row.update({
                    "enabled": bool(merged.get("enabled", True)),
                    "energyRequired": merged.get("energy_required", 0.5),
                    "maximumProductivity": merged.get("maximum_productivity", 3.0),
                    "categories": merged.get("categories", ["crafting"]),
                    "ingredients": merged.get("ingredients", []),
                    "results": merged.get("results", []),
                })
            elif kind == "items":
                row.update({
                    "stackSize": merged.get("stack_size"),
                    "flags": merged.get("flags", []),
                    "placeResult": merged.get("place_result"),
                })
            elif kind == "machines":
                row.update({
                    "craftingSpeed": merged.get("crafting_speed"),
                    "craftingCategories": merged.get("crafting_categories", []),
                    "moduleSlots": merged.get("module_slots"),
                    "energyUsage": merged.get("energy_usage"),
                })
            else:
                unit = merged.get("unit") if isinstance(merged.get("unit"), dict) else {}
                row.update({
                    "enabled": bool(merged.get("enabled", True)),
                    "prerequisites": merged.get("prerequisites", []),
                    "unitCount": unit.get("count"),
                    "unitCountFormula": unit.get("count_formula"),
                    "unitTime": unit.get("time"),
                    "science": unit.get("ingredients", []),
                    "unlocks": [
                        effect.get("recipe") for effect in merged.get("effects", [])
                        if isinstance(effect, dict) and effect.get("type") == "unlock-recipe"
                        and isinstance(effect.get("recipe"), str)
                    ],
                })
            rows.append(row)
        return rows

    def validate_edit(self, kind: str, name: str, changes: Any) -> dict[str, Any]:
        _ptype, source = self._source(kind, name)
        changes = _mapping(changes, f"{kind} edit")
        allowed: set[str]
        clean: dict[str, Any] = {}
        if kind == "recipes":
            allowed = {"enabled", "energy_required", "maximum_productivity"}
            if "enabled" in changes:
                clean["enabled"] = _bool(changes["enabled"], "Recipe enabled")
            if "energy_required" in changes:
                clean["energy_required"] = _positive_number(
                    changes["energy_required"], "Recipe crafting time", minimum=0.001)
            if "maximum_productivity" in changes:
                value = _finite_number(changes["maximum_productivity"], "Maximum productivity")
                if value < 0:
                    raise FactorioDataError("Maximum productivity must be >= 0")
                clean["maximum_productivity"] = value
        elif kind == "items":
            allowed = {"stack_size"}
            if "stack_size" in changes:
                value = _uint(changes["stack_size"], "Item stack size", UINT32_MAX)
                if value < 1:
                    raise FactorioDataError("Item stack size must be at least 1")
                flags = source.get("flags", [])
                if value != 1 and (
                    _ptype in FIXED_STACK_ONE_TYPES
                    or isinstance(flags, list) and "not-stackable" in flags
                ):
                    raise FactorioDataError(
                        f"{_ptype} prototypes are restricted to stack size 1"
                    )
                clean["stack_size"] = value
        elif kind == "machines":
            allowed = {"crafting_speed"}
            if "crafting_speed" in changes:
                clean["crafting_speed"] = _positive_number(
                    changes["crafting_speed"], "Machine crafting speed")
        elif kind == "technologies":
            allowed = {"enabled", "prerequisites", "unit_count", "unit_time"}
            if "enabled" in changes:
                clean["enabled"] = _bool(changes["enabled"], "Technology enabled")
            if "prerequisites" in changes:
                values = _names(changes["prerequisites"], "Technology prerequisites")
                known = set(self._indexes["technologies"])
                for ref in values:
                    if ref == name:
                        raise FactorioDataError("A technology cannot require itself")
                    if ref not in known:
                        raise FactorioDataError(f"Unknown technology prerequisite: {ref}")
                if self._prerequisite_cycle(name, values):
                    raise FactorioDataError(
                        f"Technology prerequisites would create a cycle involving {name}"
                    )
                clean["prerequisites"] = values
            if "unit_count" in changes:
                if not isinstance(source.get("unit"), dict) or "count_formula" in source["unit"]:
                    raise FactorioDataError(
                        "Research count is editable only for technologies with a fixed unit count")
                value = _uint(changes["unit_count"], "Research unit count", UINT64_MAX)
                if value < 1:
                    raise FactorioDataError("Research unit count must be > 0")
                clean["unit_count"] = value
            if "unit_time" in changes:
                if not isinstance(source.get("unit"), dict):
                    raise FactorioDataError("Research time is unavailable for trigger-only technologies")
                # Factorio 2.1 documents this as a double with no prototype-doc
                # lower bound. Validate type/finite representation without inventing one.
                clean["unit_time"] = _finite_number(changes["unit_time"], "Research unit time")
        else:
            raise FactorioDataError(f"Unknown Factorio dataset: {kind}")
        unknown = set(changes) - allowed
        if unknown:
            raise FactorioDataError(f"Unsupported {kind} fields: {', '.join(sorted(unknown))}")
        return clean

    def _source_edit_values(self, kind: str, name: str) -> dict[str, Any]:
        _ptype, source = self._source(kind, name)
        if kind == "recipes":
            return {
                "enabled": bool(source.get("enabled", True)),
                "energy_required": source.get("energy_required", 0.5),
                "maximum_productivity": source.get("maximum_productivity", 3.0),
            }
        if kind == "items":
            return {"stack_size": source.get("stack_size")}
        if kind == "machines":
            return {"crafting_speed": source.get("crafting_speed")}
        unit = source.get("unit") if isinstance(source.get("unit"), dict) else {}
        values = {
            "enabled": bool(source.get("enabled", True)),
            "prerequisites": list(source.get("prerequisites") or []),
        }
        if "count" in unit and "count_formula" not in unit:
            values["unit_count"] = unit["count"]
        if "time" in unit:
            values["unit_time"] = unit["time"]
        return values

    def set_edit(self, kind: str, name: str, changes: Any) -> dict[str, Any]:
        clean = self.validate_edit(kind, name, changes)
        source_values = self._source_edit_values(kind, name)
        delta = {
            key: value for key, value in clean.items()
            if source_values.get(key) != value
        }
        edits = self.overrides["edits"].setdefault(kind, {})
        if delta:
            edits[name] = delta
        else:
            edits.pop(name, None)
        if not edits:
            self.overrides["edits"].pop(kind, None)
        return delta

    def discard(self, kind: str | None = None, name: str | None = None) -> None:
        edits = self.overrides["edits"]
        if kind is None:
            edits.clear()
            return
        if kind not in edits:
            return
        if name is None:
            edits.pop(kind, None)
            return
        edits[kind].pop(name, None)
        if not edits[kind]:
            edits.pop(kind, None)

    def save(self, project: Path) -> None:
        project = Path(project).expanduser().resolve()
        project.mkdir(parents=True, exist_ok=True)
        target = project / OVERRIDES_FILE
        _atomic_json(target, self.overrides)


def validate_overrides(value: Any) -> dict[str, Any]:
    value = _mapping(value, "Factorio overrides")
    if value.get("format", FORMAT_VERSION) != FORMAT_VERSION:
        raise FactorioDataError(f"Unsupported Factorio override format: {value.get('format')}")
    edits = value.get("edits", {})
    edits = _mapping(edits, "Factorio override edits")
    normalized: dict[str, dict[str, Any]] = {}
    for kind, records in edits.items():
        if kind not in KINDS:
            raise FactorioDataError(f"Unsupported override dataset: {kind}")
        records = _mapping(records, f"{kind} overrides")
        normalized[kind] = {}
        for name, changes in records.items():
            if not isinstance(name, str) or not name:
                raise FactorioDataError(f"{kind} override has an invalid prototype name")
            normalized[kind][name] = _mapping(changes, f"{kind}:{name} override")
    return {"format": FORMAT_VERSION, "edits": normalized}


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def active_mods(project: Path) -> list[str]:
    path = Path(project) / SOURCE_DIR / SOURCE_MOD_LIST
    if not path.exists():
        return []
    payload = _read_json(path, label="Factorio mod list")
    if not isinstance(payload, dict) or not isinstance(payload.get("mods"), list):
        raise FactorioDataError("Factorio mod-list.json must contain a mods array")
    names = []
    for entry in payload["mods"]:
        if not isinstance(entry, dict) or not entry.get("enabled", False):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not DEPENDENCY_NAME.fullmatch(name):
            raise FactorioDataError("Enabled mod list contains an unsafe mod name")
        if name not in names:
            names.append(name)
    return names


def _dependency_name(text: str) -> str:
    # Factorio 2.1 info.json dependencies are: optional marker, internal mod
    # name, and optional version comparison. Match the complete string so an
    # authored dependency can never smuggle arbitrary Lua/text into info.json.
    if not isinstance(text, str):
        raise FactorioDataError("Factorio dependencies must be strings")
    match = DEPENDENCY_TEXT.fullmatch(text)
    if not match:
        raise FactorioDataError(f"Invalid Factorio dependency: {text}")
    if match.group("version"):
        _bounded_mod_version(match.group("version"), "Dependency version")
    return match.group("name")


def project_manifest(project: Path) -> dict[str, Any]:
    payload = _read_json(Path(project) / PROJECT_FILE, label="Factorio project manifest")
    payload = _mapping(payload, "Factorio project manifest")
    mod = _mapping(payload.get("mod"), "Factorio project mod")
    name = mod.get("name")
    version = mod.get("version")
    if (not isinstance(name, str) or not SAFE_MOD_NAME.fullmatch(name)
            or len(name) > 100):
        raise FactorioDataError(
            "Mod name must be at most 100 letters, numbers, _ or - characters"
        )
    _bounded_mod_version(version, "Mod version")
    for key, limit in (("title", 100),):
        value = mod.get(key)
        if value is not None and (
            not isinstance(value, str) or not value.strip() or len(value) > limit
        ):
            raise FactorioDataError(f"Mod {key} must be non-empty text up to {limit} characters")
    for key in ("author", "description"):
        value = mod.get(key)
        if value is not None and not isinstance(value, str):
            raise FactorioDataError(f"Mod {key} must be text")
    dependencies = mod.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise FactorioDataError("Mod dependencies must be an array")
    for dependency in dependencies:
        _dependency_name(dependency)
    return payload


def export_dependencies(project: Path, authored: list[str], *, exclude: set[str] | None = None) -> list[str]:
    result = list(authored)
    excluded = set(exclude or ())
    names = {_dependency_name(value) for value in result}
    if "base" not in names:
        result.insert(0, "base >= 2.1.0")
        names.add("base")
    # Optional dependencies are the safe way to make this late override load
    # after enabled source mods without making those mods mandatory forever.
    for name in sorted(active_mods(project), key=str.casefold):
        if name == "base" or name in names or name in excluded:
            continue
        result.append(f"? {name}")
        names.add(name)
    return result


def _lua_quote(value: str) -> str:
    if not isinstance(value, str):
        raise FactorioDataError("Lua string value must be text")
    if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
        raise FactorioDataError("Prototype names may not contain control characters")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace(
        "\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + '"'


def _lua_value(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FactorioDataError("Cannot export a non-finite number")
        return format(value, ".15g")
    if isinstance(value, str):
        return _lua_quote(value)
    if isinstance(value, list):
        return "{" + ", ".join(_lua_value(entry) for entry in value) + "}"
    raise FactorioDataError(f"Cannot export value of type {type(value).__name__}")


def render_data_final_fixes(store: PrototypeStore) -> str:
    lines = [
        "-- Generated by Lexeditor. Do not edit source mods; this late override is separate.",
        "-- Factorio prototype stage: data-final-fixes.lua",
        "",
    ]
    edits = store.overrides["edits"]
    type_for_kind = {
        "recipes": "recipe",
        "technologies": "technology",
    }
    for kind in KINDS:
        records = edits.get(kind, {})
        for name in sorted(records, key=str.casefold):
            prototype_type, _source = store._source(kind, name)
            data_type = type_for_kind.get(kind, prototype_type)
            variable = "p"
            lines.append(
                f"do local {variable} = data.raw[{_lua_quote(data_type)}][{_lua_quote(name)}]"
            )
            lines.append("  if p then")
            changes = records[name]
            if kind == "technologies":
                for key in ("enabled", "prerequisites"):
                    if key in changes:
                        lines.append(f"    p.{key} = {_lua_value(changes[key])}")
                nested = []
                if "unit_count" in changes:
                    nested.append(("count", changes["unit_count"]))
                if "unit_time" in changes:
                    nested.append(("time", changes["unit_time"]))
                if nested:
                    lines.append("    if p.unit then")
                    for key, value in nested:
                        lines.append(f"      p.unit.{key} = {_lua_value(value)}")
                    lines.append("    end")
            else:
                for key in sorted(changes):
                    lines.append(f"    p.{key} = {_lua_value(changes[key])}")
            lines.append("  end")
            lines.append("end")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_info(project: Path) -> str:
    manifest = project_manifest(project)
    mod = manifest["mod"]
    info = {
        "name": mod["name"],
        "version": mod["version"],
        "title": mod.get("title") or mod["name"],
        "author": mod.get("author") or "Lexeditor",
        "description": mod.get("description") or "Factorio prototype overrides generated by Lexeditor.",
        "factorio_version": "2.1",
        "dependencies": export_dependencies(
            project, list(mod.get("dependencies", [])), exclude={mod["name"]}),
    }
    return json.dumps(info, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def build_mod_bytes(project: Path, store: PrototypeStore | None = None) -> tuple[str, bytes]:
    project = Path(project).expanduser().resolve()
    store = store or PrototypeStore.from_project(project)
    manifest = project_manifest(project)
    name = manifest["mod"]["name"]
    version = manifest["mod"]["version"]
    folder = f"{name}_{version}"
    files = {
        f"{folder}/info.json": render_info(project),
        f"{folder}/data-final-fixes.lua": render_data_final_fixes(store),
    }
    output = io.BytesIO()
    # Store uncompressed bytes with fixed metadata. This avoids platform/zlib
    # variation and makes identical project state produce byte-identical ZIPs.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, files[path].encode("utf-8"))
    return f"{folder}.zip", output.getvalue()


def export_mod(
        project: Path, output_dir: Path | None = None,
        *, store: PrototypeStore | None = None) -> Path:
    project = Path(project).expanduser().resolve()
    filename, payload = build_mod_bytes(project, store)
    target_dir = Path(output_dir).expanduser().resolve() if output_dir else project / "build"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target
