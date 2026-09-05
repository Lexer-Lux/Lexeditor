"""Read Junction-compatible folder metadata without adopting its load model.

Junction VIII is evidence for the package syntax only. Its MS-PL sources
``AppWrapper/Profile.cs`` and ``RuntimeVar.cs`` prove ConfigOption, ModFolder,
Conditional, ActiveWhen, ApplyTo, aliases, and the supported condition tree.
``VFile.cs`` proves that its live conditions are re-evaluated during file reads.
Lexeditor keeps one low-to-high stack and resolves layers inside each mod before
that stack is merged. Live process-memory conditions are deliberately not
evaluated here: pre-launch composition cannot reproduce that per-request hook.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET


MAX_MOD_XML_BYTES = 2 * 1024 * 1024
MAX_RUNTIME_PROGRAM_TOKENS = 256
SYSTEM_FIELDS = ("Day", "Month", "Year", "Hour", "Minute", "Second")
_COMPARISON = re.compile(
    r"^\s*([A-Za-z0-9_.-]+)\s*(<=|>=|!=|=|<|>)\s*(-?(?:0x[0-9a-fA-F]+|\d+))\s*$"
)
_WINDOWS_DEVICES = {
    "con", "prn", "aux", "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


class FolderMetadataError(ValueError):
    """The package declares a folder rule Lexeditor cannot safely parse."""


@dataclass(frozen=True)
class FolderOption:
    id: str
    name: str
    kind: str
    default: int
    values: tuple[tuple[int, str], ...]

    def json(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.kind,
            "default": self.default,
            "values": [
                {"value": value, "name": name} for value, name in self.values
            ],
        }


@dataclass(frozen=True)
class FolderLayer:
    folder: str
    kind: str
    active_when: object | None
    conditions: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class PackageRules:
    options: tuple[FolderOption, ...] = ()
    mod_folders: tuple[FolderLayer, ...] = ()
    conditionals: tuple[FolderLayer, ...] = ()
    aliases: tuple[tuple[str, str], ...] = ()

    def resolved_options(self, overrides: dict | None) -> dict[str, int]:
        supplied = overrides if isinstance(overrides, dict) else {}
        result: dict[str, int] = {}
        known = {option.id.casefold(): option for option in self.options}
        for option in self.options:
            raw = supplied.get(option.id, supplied.get(option.id.casefold(), option.default))
            if isinstance(raw, bool):
                value = int(raw)
            elif isinstance(raw, int):
                value = raw
            else:
                raise FolderMetadataError(f"Option {option.id} must be an integer")
            allowed = {item[0] for item in option.values}
            if value not in allowed:
                raise FolderMetadataError(
                    f"Option {option.id} does not allow value {value}"
                )
            result[option.id] = value
        unknown = [str(key) for key in supplied if str(key).casefold() not in known]
        if unknown:
            raise FolderMetadataError(
                "Unknown mod folder option: " + ", ".join(sorted(unknown))
            )
        return result


def _safe_folder(value: str) -> str:
    text = str(value or "").replace("\\", "/").strip("/")
    path = PurePosixPath(text)
    if (not text or path.is_absolute() or any(part in ("", ".", "..") for part in path.parts)
            or any(":" in part or part.rstrip(" .").casefold() in _WINDOWS_DEVICES
                   for part in path.parts)):
        raise FolderMetadataError(f"Unsafe mod folder path: {value}")
    return "/".join(path.parts)


def _first_element(parent: ET.Element | None) -> ET.Element | None:
    return next(iter(parent), None) if parent is not None else None


def _active_when(node: ET.Element) -> object | None:
    legacy = node.attrib.get("ActiveWhen")
    if legacy is not None:
        return ("option", legacy.strip())
    wrapper = node.find("ActiveWhen")
    child = _first_element(wrapper)
    return _active_node(child) if child is not None else None


def _active_node(node: ET.Element) -> object:
    tag = node.tag.casefold()
    if tag == "option":
        return ("option", (node.text or "").strip())
    if tag in ("and", "or"):
        return (tag, tuple(_active_node(child) for child in node))
    if tag == "not":
        child = _first_element(node)
        if child is None or len(node) != 1:
            return ("unsupported", "Not must contain exactly one condition")
        return ("not", _active_node(child))
    return ("unsupported", f"Unsupported ActiveWhen node: {node.tag}")


def _runtime_node(node: ET.Element) -> object:
    tag = node.tag.casefold()
    if tag == "runtimevar":
        return (
            "runtimevar", str(node.attrib.get("Var", "")).strip(),
            str(node.attrib.get("Values", "")).strip(),
        )
    if tag in ("and", "or"):
        return (tag, tuple(_runtime_node(child) for child in node))
    if tag == "not":
        child = _first_element(node)
        if child is None or len(node) != 1:
            return ("unsupported", "Not must contain exactly one condition")
        return ("not", _runtime_node(child))
    return ("unsupported", f"Unsupported runtime condition: {node.tag}")


def parse(data: bytes | None) -> PackageRules:
    """Parse only folder-selection metadata from one package's mod.xml."""
    if not data:
        return PackageRules()
    if len(data) > MAX_MOD_XML_BYTES:
        raise FolderMetadataError("mod.xml is larger than the supported limit")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise FolderMetadataError(f"mod.xml is not valid XML: {error}") from error
    if root.tag.casefold() != "modinfo":
        raise FolderMetadataError("mod.xml must have a ModInfo root")

    options: list[FolderOption] = []
    seen_options: set[str] = set()
    for node in root.findall("ConfigOption"):
        option_id = (node.findtext("ID") or "").strip()
        kind = (node.findtext("Type") or "").strip()
        if not option_id or option_id.casefold() in seen_options:
            raise FolderMetadataError("Every ConfigOption must have a unique ID")
        if kind.casefold() not in ("bool", "list"):
            raise FolderMetadataError(f"Unsupported option type for {option_id}: {kind}")
        try:
            default = int((node.findtext("Default") or "").strip(), 0)
        except ValueError as error:
            raise FolderMetadataError(f"Option {option_id} has an invalid default") from error
        values: list[tuple[int, str]] = []
        if kind.casefold() == "bool":
            values = [(0, "Off"), (1, "On")]
        else:
            for choice in node.findall("Option"):
                try:
                    value = int(str(choice.attrib.get("Value", "")).strip(), 0)
                except ValueError as error:
                    raise FolderMetadataError(
                        f"Option {option_id} has an invalid list value"
                    ) from error
                values.append((value, str(choice.attrib.get("Name", value))))
        if not values or default not in {value for value, _name in values}:
            raise FolderMetadataError(f"Option {option_id} has no valid default choice")
        seen_options.add(option_id.casefold())
        options.append(FolderOption(
            option_id, (node.findtext("Name") or option_id).strip(),
            kind.casefold(), default, tuple(values),
        ))

    mod_folders = tuple(
        FolderLayer(_safe_folder(node.attrib.get("Folder", "")), "option", _active_when(node))
        for node in root.findall("ModFolder")
    )
    conditionals: list[FolderLayer] = []
    for node in root.findall("Conditional"):
        conditions: dict[str, object] = {}
        for child in node:
            if child.tag.casefold() == "activewhen":
                continue
            apply_to = str(child.attrib.get("ApplyTo", "")).replace("\\", "/").strip("/")
            if apply_to:
                apply_to = str(PurePosixPath(apply_to)).replace("\\", "/")
                if apply_to.startswith("../") or "/../" in f"/{apply_to}/":
                    raise FolderMetadataError(f"Unsafe ApplyTo path: {apply_to}")
            conditions[apply_to.casefold()] = _runtime_node(child)
        conditionals.append(FolderLayer(
            _safe_folder(node.attrib.get("Folder", "")), "runtime", _active_when(node),
            tuple(conditions.items()),
        ))
    aliases = tuple(
        (str(node.attrib.get("Name", "")).strip(), (node.text or "").strip())
        for node in root.findall("Variable") if str(node.attrib.get("Name", "")).strip()
    )
    return PackageRules(tuple(options), mod_folders, tuple(conditionals), aliases)


def system_state(now: datetime | None = None) -> dict[str, int]:
    value = now or datetime.now().astimezone()
    return {
        "Day": value.day, "Month": value.month, "Year": value.year,
        "Hour": value.hour, "Minute": value.minute, "Second": value.second,
    }


def _integer(text: str) -> int:
    value = text.strip()
    return int(value, 16 if value.casefold().startswith("0x") else 10)


def _compare(actual: int, values: str) -> bool:
    if ".." in values:
        parts = [part for part in values.split("..") if part.strip()]
        if len(parts) != 2:
            raise FolderMetadataError(f"Invalid RuntimeVar range: {values}")
        low, high = (_integer(part) for part in parts)
        return low <= actual <= high
    choices = [_integer(part) for part in values.split(",") if part.strip()]
    if not choices:
        raise FolderMetadataError(f"RuntimeVar has no values: {values}")
    return actual in choices


def _option_test(spec: str, options: dict[str, int], ffnx: dict[str, int]) -> tuple[bool, str]:
    match = _COMPARISON.fullmatch(spec)
    if not match:
        return False, f"Unsupported option expression: {spec}"
    name, operator, raw_expected = match.groups()
    source = ffnx if name.casefold().startswith("ffnx_") else options
    lookup = name[5:] if source is ffnx else name
    found = next((value for key, value in source.items() if key.casefold() == lookup.casefold()), None)
    if found is None:
        return False, f"No value is available for option {name}"
    expected = _integer(raw_expected)
    tests = {
        "=": found == expected, "!=": found != expected,
        "<": found < expected, ">": found > expected,
        "<=": found <= expected, ">=": found >= expected,
    }
    return tests[operator], ""


def _eval_active(tree: object | None, options: dict[str, int],
                 ffnx: dict[str, int]) -> tuple[bool, str]:
    if tree is None:
        return True, ""
    kind = tree[0]
    if kind == "option":
        return _option_test(tree[1], options, ffnx)
    if kind == "unsupported":
        return False, tree[1]
    if kind == "not":
        active, reason = _eval_active(tree[1], options, ffnx)
        return (False, reason) if reason else (not active, "")
    results = [_eval_active(child, options, ffnx) for child in tree[1]]
    reasons = [reason for _active, reason in results if reason]
    if reasons:
        return False, "; ".join(reasons)
    return ((all(active for active, _reason in results) if kind == "and"
             else any(active for active, _reason in results)), "")


def _eval_runtime(tree: object, aliases: dict[str, str], system: dict[str, int]) -> tuple[bool, str]:
    kind = tree[0]
    if kind == "unsupported":
        return False, tree[1]
    if kind == "runtimevar":
        variable = aliases.get(tree[1].casefold(), tree[1])
        parts = variable.split(":")
        if len(parts) != 2 or parts[0].casefold() != "sys":
            return False, (
                f"RuntimeVar {tree[1]} requires live process state; "
                "pre-launch composition leaves it inactive"
            )
        field = next((name for name in SYSTEM_FIELDS if name.casefold() == parts[1].casefold()), None)
        if field is None or field not in system:
            return False, f"Unsupported system RuntimeVar: {variable}"
        try:
            return _compare(int(system[field]), tree[2]), ""
        except (TypeError, ValueError, FolderMetadataError) as error:
            return False, str(error)
    if kind == "not":
        active, reason = _eval_runtime(tree[1], aliases, system)
        return (False, reason) if reason else (not active, "")
    results = [_eval_runtime(child, aliases, system) for child in tree[1]]
    reasons = [reason for _active, reason in results if reason]
    if reasons:
        return False, "; ".join(reasons)
    return ((all(active for active, _reason in results) if kind == "and"
             else any(active for active, _reason in results)), "")


def select_layers(rules: PackageRules, option_values: dict | None,
                  state: dict | None = None) -> tuple[list[FolderLayer], list[dict], dict[str, int]]:
    """Select pre-launch layers and explain every inactive or unsupported rule."""
    runtime = state if isinstance(state, dict) else {}
    system = runtime.get("system") if isinstance(runtime.get("system"), dict) else system_state()
    ffnx = runtime.get("ffnx") if isinstance(runtime.get("ffnx"), dict) else {}
    options = rules.resolved_options(option_values)
    aliases = {name.casefold(): value for name, value in rules.aliases}
    selected: list[FolderLayer] = []
    report: list[dict] = []
    for layer in (*rules.mod_folders, *rules.conditionals):
        active, reason = _eval_active(layer.active_when, options, ffnx)
        if active and layer.kind == "runtime" and not layer.conditions:
            active, reason = False, "Conditional folder has no file condition"
        # A runtime folder can contain path-specific conditions. It remains a
        # candidate layer here; each file is filtered below.
        if active:
            selected.append(layer)
        report.append({
            "folder": layer.folder, "kind": layer.kind,
            "active": active, "reason": reason,
        })
    return selected, report, options


def condition_for_file(layer: FolderLayer, relative: str, rules: PackageRules,
                       state: dict | None = None) -> tuple[bool, str]:
    if layer.kind != "runtime":
        return True, ""
    conditions = dict(layer.conditions)
    tree = conditions.get(relative.casefold(), conditions.get(""))
    if tree is None:
        return False, f"Conditional folder has no condition for {relative}"
    runtime = state if isinstance(state, dict) else {}
    system = runtime.get("system") if isinstance(runtime.get("system"), dict) else system_state()
    aliases = {name.casefold(): value for name, value in rules.aliases}
    return _eval_runtime(tree, aliases, system)


def runtime_program(layer: FolderLayer, relative: str,
                    rules: PackageRules) -> list[dict] | None:
    """Return one package condition as a bounded postfix program.

    This is data for Lexeditor's future FFNx-side evaluator, not executable
    package code.  Keeping the parsed condition tree in the composed runtime
    prevents a later implementation from having to reopen an editable folder
    or IROJ archive after the game starts.
    """
    if layer.kind != "runtime":
        return None
    conditions = dict(layer.conditions)
    tree = conditions.get(relative.casefold(), conditions.get(""))
    if tree is None:
        return None
    aliases = {name.casefold(): value for name, value in rules.aliases}
    program: list[dict] = []

    def emit(node: object) -> None:
        kind = node[0]
        if kind == "runtimevar":
            variable = aliases.get(str(node[1]).casefold(), str(node[1]))
            program.append({"op": "var", "spec": variable, "values": str(node[2])})
            return
        if kind == "unsupported":
            program.append({"op": "unsupported", "reason": str(node[1])})
            return
        if kind == "not":
            emit(node[1])
            program.append({"op": "not", "arity": 1})
            return
        for child in node[1]:
            emit(child)
        program.append({"op": kind, "arity": len(node[1])})

    emit(tree)
    if len(program) > MAX_RUNTIME_PROGRAM_TOKENS:
        return [{
            "op": "unsupported",
            "reason": f"Runtime condition exceeds {MAX_RUNTIME_PROGRAM_TOKENS} tokens",
        }]
    return program
