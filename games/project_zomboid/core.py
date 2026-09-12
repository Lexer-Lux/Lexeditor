"""Conservative Project Zomboid Build 42 project readers and writers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Iterable


ITEM_TYPES = (
    "base:alarmclock",
    "base:alarmclockclothing",
    "base:animal",
    "base:clothing",
    "base:container",
    "base:drainable",
    "base:food",
    "base:key",
    "base:literature",
    "base:map",
    "base:moveable",
    "base:normal",
    "base:radio",
    "base:weapon",
    "base:weaponpart",
)
MOD_INFO_SCALAR_FIELDS = (
    "name",
    "id",
    "author",
    "modversion",
    "description",
    "icon",
    "url",
    "versionMin",
    "versionMax",
    "require",
    "incompatible",
    "loadModAfter",
    "loadModBefore",
    "category",
)
ITEM_EDITABLE_FIELDS = ("ItemType", "Weight", "Icon", "DisplayCategory")
SCRIPT_ROOTS = ("common/media/scripts", "42/media/scripts")
IGNORED_DEPLOY_NAMES = {".git", ".lexeditor", ".pytest_cache", "__pycache__"}
_VERSION_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
_INFO_LINE_RE = re.compile(r"^(?P<prefix>\s*)(?P<key>[A-Za-z][A-Za-z0-9_]*)\s*=(?P<value>.*?)(?P<ending>\r?\n)?$")
_PROPERTY_RE = re.compile(
    r"(?m)^(?P<prefix>[ \t]*)(?P<key>[A-Za-z][A-Za-z0-9_]*)"
    r"(?P<space1>[ \t]*)=(?P<space2>[ \t]*)(?P<value>[^\r\n,{}]*?)"
    r"(?P<space3>[ \t]*),(?P<suffix>[^\r\n]*)(?P<ending>\r?\n|$)"
)
_ASSIGNMENT_RE = re.compile(r"\b(?P<key>[A-Za-z][A-Za-z0-9_]*)[ \t]*=")


class ProjectZomboidError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def project_root() -> Path:
    value = os.environ.get("LEXEDITOR_PROJECT_ZOMBOID_PROJECT")
    if not value:
        raise ProjectZomboidError("No Project Zomboid project is selected")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ProjectZomboidError(f"Project folder does not exist: {root}")
    return root


def user_zomboid_root() -> Path:
    return Path(os.environ.get(
        "LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT",
        Path.home() / "Zomboid",
    )).expanduser().resolve()


def _inside(root: Path, target: Path) -> bool:
    root = root.resolve()
    target = target.resolve()
    return target == root or root in target.parents


def _safe_relative(root: Path, value: str) -> Path:
    relative = Path(value.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ProjectZomboidError("Path must stay inside the selected project")
    target = (root / relative).resolve()
    if not _inside(root, target):
        raise ProjectZomboidError("Path escapes the selected project")
    return target


def mod_info_path(root: Path) -> Path:
    for relative in ("42/mod.info", "common/mod.info", "mod.info"):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    raise ProjectZomboidError("Project has no supported Build 42 mod.info")


def _read_utf8(path: Path) -> tuple[bytes, str]:
    data = path.read_bytes()
    try:
        return data, data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ProjectZomboidError(f"{path.name} is not UTF-8 text") from error


def read_mod_info(root: Path) -> dict:
    path = mod_info_path(root)
    data, text = _read_utf8(path)
    values: dict[str, str] = {}
    duplicates: set[str] = set()
    unknown: list[str] = []
    for line in text.splitlines():
        match = _INFO_LINE_RE.match(line)
        if not match:
            if line.strip() and not line.lstrip().startswith(("#", "//")):
                unknown.append(line.strip())
            continue
        key = match.group("key")
        value = match.group("value").strip()
        if key in values:
            duplicates.add(key)
        else:
            values[key] = value
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(data),
        "fields": {key: values.get(key, "") for key in MOD_INFO_SCALAR_FIELDS},
        "duplicateKeys": sorted(duplicates),
        "unmodeledLines": len(unknown),
    }


def _clean_scalar(value: object, field: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise ProjectZomboidError(f"{field} must be text")
    clean = value.strip()
    if any(character in clean for character in "\r\n\x00"):
        raise ProjectZomboidError(f"{field} cannot contain line breaks")
    if not allow_empty and not clean:
        raise ProjectZomboidError(f"{field} cannot be empty")
    return clean


def _validate_mod_info(fields: dict[str, str]) -> None:
    _clean_scalar(fields.get("name", ""), "name", allow_empty=False)
    identifier = _clean_scalar(fields.get("id", ""), "id", allow_empty=False)
    if any(character in identifier for character in ",;="):
        raise ProjectZomboidError("id cannot contain ',', ';', or '='")
    for key in ("versionMin", "versionMax"):
        value = fields.get(key, "").strip()
        if value and not _VERSION_RE.fullmatch(value):
            raise ProjectZomboidError(f"{key} must look like 42.20 or 42.20.4")


def save_mod_info(root: Path, expected_sha256: str, edits: dict) -> dict:
    path = mod_info_path(root)
    data, text = _read_utf8(path)
    if sha256_bytes(data) != expected_sha256:
        raise ProjectZomboidError("mod.info changed outside Lexeditor; reload before saving")
    if not isinstance(edits, dict) or set(edits) - set(MOD_INFO_SCALAR_FIELDS):
        raise ProjectZomboidError("Save contains unsupported mod.info fields")

    current = read_mod_info(root)
    duplicate_edit = set(current["duplicateKeys"]) & set(edits)
    if duplicate_edit:
        raise ProjectZomboidError(
            "Cannot safely edit duplicated mod.info keys: " + ", ".join(sorted(duplicate_edit))
        )

    proposed = dict(current["fields"])
    for key, value in edits.items():
        proposed[key] = _clean_scalar(value, key)
    _validate_mod_info(proposed)

    remaining = {key: proposed[key] for key in edits}
    output: list[str] = []
    newline = "\r\n" if "\r\n" in text else "\n"
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        match = _INFO_LINE_RE.match(bare)
        if match and match.group("key") in remaining:
            key = match.group("key")
            ending = line[len(bare):]
            output.append(f"{match.group('prefix')}{key}={remaining.pop(key)}{ending}")
        else:
            output.append(line)
    if remaining:
        if output and not output[-1].endswith(("\n", "\r")):
            output[-1] += newline
        for key in MOD_INFO_SCALAR_FIELDS:
            if key in remaining:
                output.append(f"{key}={remaining[key]}{newline}")

    replacement = "".join(output).encode("utf-8")
    _atomic_write(path, replacement)
    return read_mod_info(root)


@dataclass(frozen=True)
class Block:
    kind: str
    name: str
    start: int
    open_brace: int
    close_brace: int


def _masked_code(text: str) -> str:
    """Blank strings/comments while preserving indexes and braces outside them."""
    chars = list(text)
    i = 0
    state = "code"
    quote = ""
    while i < len(chars):
        c = chars[i]
        n = chars[i + 1] if i + 1 < len(chars) else ""
        if state == "code":
            if c in "\"'":
                quote = c
                state = "string"
                chars[i] = " "
            elif c == "/" and n == "/":
                chars[i] = chars[i + 1] = " "
                state = "line"
                i += 1
            elif c == "/" and n == "*":
                chars[i] = chars[i + 1] = " "
                state = "block"
                i += 1
        elif state == "string":
            if c == "\\" and i + 1 < len(chars):
                chars[i] = chars[i + 1] = " "
                i += 1
            else:
                chars[i] = " "
                if c == quote:
                    state = "code"
        elif state == "line":
            if c in "\r\n":
                state = "code"
            else:
                chars[i] = " "
        elif state == "block":
            chars[i] = " "
            if c == "*" and n == "/":
                chars[i + 1] = " "
                state = "code"
                i += 1
        i += 1
    return "".join(chars)


def _matching_brace(masked: str, open_index: int, limit: int | None = None) -> int:
    depth = 0
    stop = len(masked) if limit is None else min(limit, len(masked))
    for index in range(open_index, stop):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return index
            if depth < 0:
                break
    raise ProjectZomboidError("Unbalanced script braces")


def _top_level_blocks(text: str, kind: str, start: int = 0, end: int | None = None) -> list[Block]:
    masked = _masked_code(text)
    stop = len(text) if end is None else end
    pattern = re.compile(rf"\b{re.escape(kind)}\s+([A-Za-z0-9_.-]+)\s*\{{")
    blocks: list[Block] = []
    cursor = start
    depth = 0
    while cursor < stop:
        match = pattern.search(masked, cursor, stop)
        if not match:
            break
        for c in masked[cursor:match.start()]:
            if c == "{":
                depth += 1
            elif c == "}":
                depth = max(0, depth - 1)
        if depth == 0:
            open_brace = masked.find("{", match.start(), match.end())
            close_brace = _matching_brace(masked, open_brace, stop)
            blocks.append(Block(kind, match.group(1), match.start(), open_brace, close_brace))
            cursor = close_brace + 1
        else:
            cursor = match.end()
    return blocks


def _module_item_blocks(text: str) -> list[tuple[Block, Block]]:
    masked = _masked_code(text)
    modules = _top_level_blocks(text, "module")
    found: list[tuple[Block, Block]] = []
    item_pattern = re.compile(r"\bitem\s+([A-Za-z0-9_.-]+)\s*\{")
    for module in modules:
        cursor = module.open_brace + 1
        depth = 0
        while cursor < module.close_brace:
            match = item_pattern.search(masked, cursor, module.close_brace)
            if not match:
                break
            for c in masked[cursor:match.start()]:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth = max(0, depth - 1)
            if depth == 0:
                open_brace = masked.find("{", match.start(), match.end())
                close_brace = _matching_brace(masked, open_brace, module.close_brace)
                found.append((
                    module,
                    Block("item", match.group(1), match.start(), open_brace, close_brace),
                ))
                cursor = close_brace + 1
            else:
                cursor = match.end()
    return found


def _top_level_property_counts(text: str, block: Block, keys: Iterable[str]) -> dict[str, int]:
    """Count selected assignments regardless of line layout, ignoring nested grammar."""
    wanted = set(keys)
    counts = {key: 0 for key in wanted}
    if not wanted:
        return counts
    body = text[block.open_brace + 1:block.close_brace]
    masked = _masked_code(body)
    curly = square = paren = 0
    cursor = 0
    for match in _ASSIGNMENT_RE.finditer(masked):
        for c in masked[cursor:match.start()]:
            if c == "{":
                curly += 1
            elif c == "}":
                curly = max(0, curly - 1)
            elif c == "[":
                square += 1
            elif c == "]":
                square = max(0, square - 1)
            elif c == "(":
                paren += 1
            elif c == ")":
                paren = max(0, paren - 1)
        cursor = match.end()
        key = match.group("key")
        if curly == 0 and square == 0 and paren == 0 and key in counts:
            counts[key] += 1
    return counts


def _properties(text: str, block: Block) -> tuple[dict[str, str], set[str]]:
    body = text[block.open_brace + 1:block.close_brace]
    values: dict[str, str] = {}
    duplicates: set[str] = set()
    masked = _masked_code(body)
    depth = 0
    line_start = 0
    for match in _PROPERTY_RE.finditer(body):
        for c in masked[line_start:match.start()]:
            if c == "{":
                depth += 1
            elif c == "}":
                depth = max(0, depth - 1)
        line_start = match.end()
        if depth != 0:
            continue
        key = match.group("key")
        value = match.group("value").strip()
        if key in values:
            duplicates.add(key)
        else:
            values[key] = value
    duplicates.update(
        key for key, count in _top_level_property_counts(text, block, values).items()
        if count > 1
    )
    return values, duplicates


def script_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for relative in SCRIPT_ROOTS:
        base = root / relative
        if base.is_dir():
            paths.extend(path for path in base.rglob("*.txt") if path.is_file() and not path.is_symlink())
    return sorted(set(paths), key=lambda path: path.relative_to(root).as_posix().casefold())


def read_items(root: Path) -> dict:
    rows = []
    errors = []
    for path in script_paths(root):
        data, text = _read_utf8(path)
        relative = path.relative_to(root).as_posix()
        try:
            pairs = _module_item_blocks(text)
        except ProjectZomboidError as error:
            errors.append({"path": relative, "error": str(error)})
            continue
        for module, block in pairs:
            values, duplicates = _properties(text, block)
            rows.append({
                "key": f"{relative}:{module.name}.{block.name}",
                "path": relative,
                "module": module.name,
                "id": block.name,
                "fullType": f"{module.name}.{block.name}",
                "sha256": sha256_bytes(data),
                "fields": {key: values.get(key, "") for key in ITEM_EDITABLE_FIELDS},
                "duplicateKeys": sorted(set(duplicates) & set(ITEM_EDITABLE_FIELDS)),
                "itemTypeOptions": list(ITEM_TYPES),
            })
    return {"rows": rows, "errors": errors}


def _validate_item_edit(key: str, value: object) -> str:
    clean = _clean_scalar(value, key)
    if "," in clean or "{" in clean or "}" in clean:
        raise ProjectZomboidError(f"{key} contains script punctuation")
    if key == "ItemType":
        if clean not in ITEM_TYPES:
            raise ProjectZomboidError("ItemType is not a Build 42 item class")
    elif key == "Weight":
        try:
            number = float(clean)
        except ValueError as error:
            raise ProjectZomboidError("Weight must be a number") from error
        if not math.isfinite(number) or number < 0:
            raise ProjectZomboidError("Weight must be a finite number >= 0")
    return clean


def save_item(root: Path, relative: str, module_name: str, item_id: str,
              expected_sha256: str, edits: dict) -> dict:
    path = _safe_relative(root, relative)
    if path not in script_paths(root):
        raise ProjectZomboidError("Script is outside supported Build 42 script roots")
    data, text = _read_utf8(path)
    if sha256_bytes(data) != expected_sha256:
        raise ProjectZomboidError("Script changed outside Lexeditor; reload before saving")
    if not isinstance(edits, dict) or not edits or set(edits) - set(ITEM_EDITABLE_FIELDS):
        raise ProjectZomboidError("Save contains unsupported item fields")

    matches = [
        (module, block)
        for module, block in _module_item_blocks(text)
        if module.name == module_name and block.name == item_id
    ]
    if len(matches) != 1:
        raise ProjectZomboidError("Item identity is missing or ambiguous")
    _module, block = matches[0]
    values, duplicates = _properties(text, block)
    unsafe = set(duplicates) & set(edits)
    if unsafe:
        raise ProjectZomboidError("Cannot safely edit duplicated item properties: " + ", ".join(sorted(unsafe)))
    missing = set(edits) - set(values)
    if missing:
        raise ProjectZomboidError(
            "This first writer changes existing scalar properties only; missing: "
            + ", ".join(sorted(missing))
        )

    clean_edits = {key: _validate_item_edit(key, value) for key, value in edits.items()}
    body_start = block.open_brace + 1
    body = text[body_start:block.close_brace]
    matches_by_key: dict[str, list[re.Match[str]]] = {key: [] for key in clean_edits}
    masked = _masked_code(body)
    depth = 0
    scan = 0
    for match in _PROPERTY_RE.finditer(body):
        for c in masked[scan:match.start()]:
            if c == "{":
                depth += 1
            elif c == "}":
                depth = max(0, depth - 1)
        scan = match.end()
        key = match.group("key")
        if depth == 0 and key in matches_by_key:
            matches_by_key[key].append(match)
    if any(len(found) != 1 for found in matches_by_key.values()):
        raise ProjectZomboidError("Item property layout became ambiguous")

    replacements: list[tuple[int, int, str]] = []
    for key, found in matches_by_key.items():
        match = found[0]
        start = body_start + match.start("value")
        end = body_start + match.end("value")
        replacements.append((start, end, clean_edits[key]))
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]

    _atomic_write(path, text.encode("utf-8"))
    rows = read_items(root)["rows"]
    saved = next(
        row for row in rows
        if row["path"] == relative and row["module"] == module_name and row["id"] == item_id
    )
    return saved


def data_map(root: Path) -> dict:
    rows = []
    try:
        info = read_mod_info(root)
        rows.append({
            "filename": info["path"],
            "status": "structured",
            "editor": "Mod Metadata",
            "notes": "Build 42 mod.info; modeled scalar keys are editable and unknown keys are preserved.",
        })
    except ProjectZomboidError:
        pass

    item_result = read_items(root)
    item_paths = {row["path"] for row in item_result["rows"]}
    error_paths = {row["path"] for row in item_result["errors"]}
    for path in script_paths(root):
        relative = path.relative_to(root).as_posix()
        rows.append({
            "filename": relative,
            "status": "partial" if relative in item_paths else "recognized",
            "editor": "Items" if relative in item_paths else "",
            "notes": (
                "Item blocks are recognized; ItemType, Weight, Icon and DisplayCategory "
                "are editable when already present. Other script blocks/properties are preserved."
                if relative in item_paths else
                "Script file is recognized but has no currently modeled item blocks."
            ),
        })
    for relative in sorted(error_paths):
        rows.append({
            "filename": relative,
            "status": "recognized",
            "editor": "",
            "notes": "Script parsing failed closed; file remains untouched.",
        })

    for relative, label in (
        ("42/media/lua", "Lua"),
        ("common/media/lua", "Lua"),
        ("42/media/textures", "Textures"),
        ("common/media/textures", "Textures"),
        ("42/media/maps", "Maps"),
        ("common/media/maps", "Maps"),
    ):
        path = root / relative
        if path.exists():
            rows.append({
                "filename": relative + "/**",
                "status": "recognized",
                "editor": "",
                "notes": f"{label} content is preserved/deployed but not structured yet.",
            })
    return {"rows": rows}


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".lexeditor.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _iter_deploy_files(root: Path) -> Iterable[tuple[Path, Path]]:
    for path in root.rglob("*"):
        if any(part in IGNORED_DEPLOY_NAMES for part in path.relative_to(root).parts):
            continue
        if path.is_symlink():
            raise ProjectZomboidError(f"Deployment refuses links: {path.relative_to(root)}")
        if path.is_file():
            if path.name.endswith((".lexeditor.tmp", ".lexeditor.bak")):
                continue
            yield path, path.relative_to(root)


def _tree_digest(root: Path) -> dict[str, str]:
    if root.is_symlink():
        raise ProjectZomboidError("Deployed mod root is a link")
    if not root.is_dir():
        return {}
    result: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ProjectZomboidError("Deployed mod contains a link")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256_file(path)
    return result


def _deployment_state_path(root: Path) -> Path:
    return root / ".lexeditor" / "project-zomboid-deployment.json"


def _local_target(root: Path, user_root: Path | None = None) -> Path:
    name = root.name.strip()
    if not name or name in {".", ".."} or any(c in name for c in '<>:"/\\|?*'):
        raise ProjectZomboidError("Project folder name is not safe for local deployment")
    base_root = user_zomboid_root() if user_root is None else Path(user_root).expanduser().resolve()
    local_root = base_root / "mods"
    target = (local_root / name).resolve()
    if not _inside(local_root, target):
        raise ProjectZomboidError("Local deployment path escaped Zomboid/mods")
    return target


def _expected_recorded_target(
    root: Path, target: Path | None, user_root: Path | None = None
) -> bool:
    if target is None:
        return False
    try:
        expected_target = _local_target(root, user_root)
    except ProjectZomboidError:
        return False
    return target == expected_target


def deployment_state(root: Path, user_root: Path | None = None) -> dict:
    state_path = _deployment_state_path(root)
    state = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            state = {}
    target_value = state.get("target") if isinstance(state, dict) else None
    target = Path(target_value) if isinstance(target_value, str) and target_value else None
    target_is_expected = _expected_recorded_target(root, target, user_root)
    deployed = bool(
        target_is_expected and target is not None
        and not target.is_symlink() and target.is_dir()
    )
    current = _tree_digest(target) if deployed and target is not None else {}
    expected = state.get("files") if isinstance(state.get("files"), dict) else {}
    owned = bool(deployed and current == expected)
    return {
        "target": str(target) if target else "",
        "deployed": deployed,
        "owned": owned,
        "externalChanges": bool(deployed and expected and current != expected),
        "fileCount": len(current),
    }


def deploy(root: Path) -> dict:
    info = read_mod_info(root)
    _validate_mod_info(info["fields"])
    target = _local_target(root)
    state_path = _deployment_state_path(root)
    previous = {}
    if state_path.is_file():
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
        except (ValueError, OSError, TypeError):
            previous = {}

    if target.exists():
        if not target.is_dir() or target.is_symlink():
            raise ProjectZomboidError(f"Deployment target is not a normal folder: {target}")
        expected = previous.get("files") if previous.get("target") == str(target) else None
        if not isinstance(expected, dict) or _tree_digest(target) != expected:
            raise ProjectZomboidError("Local mod folder is unowned or changed externally; refusing to overwrite it")

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".lexeditor-pz-stage-", dir=target.parent))
    backup: Path | None = None
    try:
        for source, relative in _iter_deploy_files(root):
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        new_files = _tree_digest(stage)
        if target.exists():
            backup = Path(tempfile.mkdtemp(prefix=".lexeditor-pz-backup-", dir=target.parent))
            backup.rmdir()
            os.replace(target, backup)
        os.replace(stage, target)
        stage = Path()
        try:
            _atomic_write(
                state_path,
                (json.dumps({
                    "schema": 1,
                    "target": str(target),
                    "files": new_files,
                }, indent=2) + "\n").encode("utf-8"),
            )
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            if backup is not None and backup.exists():
                os.replace(backup, target)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
            backup = None
    except Exception:
        if stage and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    return deployment_state(root)


def undeploy(root: Path) -> dict:
    state_path = _deployment_state_path(root)
    if not state_path.is_file():
        raise ProjectZomboidError("Lexeditor has no owned local deployment to remove")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise ProjectZomboidError("Deployment ownership state is invalid") from error
    target_value = state.get("target") if isinstance(state, dict) else None
    target = Path(target_value) if isinstance(target_value, str) and target_value else None
    if not _expected_recorded_target(root, target):
        raise ProjectZomboidError("Recorded deployment target is outside the expected Zomboid/mods folder")
    if target is None or target.is_symlink() or not target.is_dir():
        raise ProjectZomboidError("Owned local deployment is missing or unsafe")
    expected = state.get("files")
    if not isinstance(expected, dict):
        raise ProjectZomboidError("Deployment ownership state is invalid")
    if _tree_digest(target) != expected:
        raise ProjectZomboidError("Local mod changed externally; refusing to remove it")
    shutil.rmtree(target)
    state_path.unlink()
    return deployment_state(root)
