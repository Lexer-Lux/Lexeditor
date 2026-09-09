"""Bannerlord project, MSBuild, source, and build helpers."""

from __future__ import annotations

from pathlib import Path
import html
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from .module_data import read_submodule
from .paths import clear_write_helper, contained_project_path


EDITABLE_PROJECT_PROPERTIES = (
    "TargetFramework",
    "LangVersion",
    "Nullable",
    "AssemblyName",
    "RootNamespace",
    "BannerlordDir",
    "GameBin",
    "HarmonyBin",
    "McmBin",
    "ModuleDir",
    "OutputPath",
    "AppendTargetFrameworkToOutputPath",
    "CopyLocalLockFileAssemblies",
)

_TEXT_SUFFIXES = {
    ".cs", ".xml", ".txt", ".csproj", ".json", ".ini", ".config",
    ".md", ".yml", ".yaml", ".props", ".targets",
}
_MODULE_ID = re.compile(r"[A-Za-z0-9_.-]+")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _mask_xml_non_markup(value: str) -> str:
    """Blank comment/CDATA bodies while preserving all character offsets."""
    pattern = re.compile(r"<!--.*?-->|<!\[CDATA\[.*?\]\]>", re.DOTALL)
    def mask(match: re.Match) -> str:
        return "".join("\n" if char == "\n" else "\r" if char == "\r" else " " for char in match.group(0))
    return pattern.sub(mask, value)


def _project_files(project: Path) -> list[Path]:
    return sorted(path for path in project.glob("*.csproj") if path.is_file())


def primary_project_file(project: Path) -> Path | None:
    root = project.resolve()
    files = _project_files(root)
    if not files:
        return None
    target = files[0].resolve()
    if target != root and root not in target.parents:
        raise ValueError("Project file must stay inside the selected Bannerlord project")
    if target.suffix.casefold() != ".csproj" or not target.is_file():
        raise FileNotFoundError(target)
    return target


def _resolve_project_file(project: Path, requested: str | None = None) -> Path:
    root = project.resolve()
    if requested:
        target = (root / requested).resolve()
    else:
        candidate = primary_project_file(project)
        if candidate is None:
            raise FileNotFoundError(f"No .csproj found in {project}")
        target = candidate.resolve()
    if target != root and root not in target.parents:
        raise ValueError("Project file must stay inside the selected Bannerlord project")
    if target.suffix.casefold() != ".csproj" or not target.is_file():
        raise FileNotFoundError(target)
    return target


def read_project_file(path: Path) -> dict:
    """Inspect an SDK-style or classic MSBuild project without evaluating it."""
    tree = ET.parse(path)
    root = tree.getroot()
    properties: dict[str, str] = {}
    property_rows = []
    references = []
    packages = []
    items = []
    targets = []

    for group_index, group in enumerate(root):
        name = _local_name(group.tag)
        if name == "PropertyGroup":
            group_condition = group.attrib.get("Condition", "")
            for element in group:
                property_name = _local_name(element.tag)
                value = (element.text or "").strip()
                if property_name not in properties:
                    properties[property_name] = value
                property_rows.append(
                    {
                        "group": group_index,
                        "name": property_name,
                        "value": value,
                        "condition": element.attrib.get("Condition", ""),
                        "groupCondition": group_condition,
                        "editable": property_name in EDITABLE_PROJECT_PROPERTIES,
                    }
                )
        elif name == "ItemGroup":
            for element in group:
                item_name = _local_name(element.tag)
                row = {
                    "type": item_name,
                    "include": element.attrib.get("Include", ""),
                    "remove": element.attrib.get("Remove", ""),
                    "update": element.attrib.get("Update", ""),
                    "condition": element.attrib.get("Condition", ""),
                    "metadata": {
                        _local_name(child.tag): (child.text or "").strip()
                        for child in element
                    },
                }
                items.append(row)
                if item_name == "Reference":
                    references.append(row)
                elif item_name == "PackageReference":
                    packages.append(row)
        elif name == "Target":
            targets.append(
                {
                    "name": group.attrib.get("Name", ""),
                    "afterTargets": group.attrib.get("AfterTargets", ""),
                    "beforeTargets": group.attrib.get("BeforeTargets", ""),
                    "condition": group.attrib.get("Condition", ""),
                    "tasks": [_local_name(child.tag) for child in group],
                }
            )

    property_definitions: dict[str, list[dict]] = {}
    for row in property_rows:
        property_definitions.setdefault(row["name"], []).append(row)
    ambiguous_properties: dict[str, str] = {}
    editable_properties = []
    for property_name in EDITABLE_PROJECT_PROPERTIES:
        rows = property_definitions.get(property_name, [])
        if len(rows) > 1:
            ambiguous_properties[property_name] = f"defined {len(rows)} times in this project file"
            continue
        if rows and (rows[0].get("condition") or rows[0].get("groupCondition")):
            ambiguous_properties[property_name] = "defined under an MSBuild Condition"
            continue
        editable_properties.append(property_name)

    return {
        "path": str(path),
        "name": path.name,
        "sdk": root.attrib.get("Sdk", ""),
        "properties": properties,
        "propertyRows": property_rows,
        "editableProperties": editable_properties,
        "ambiguousProperties": ambiguous_properties,
        "references": references,
        "packages": packages,
        "items": items,
        "targets": targets,
    }


def save_project_properties(path: Path, edits: dict) -> dict:
    """Patch a conservative set of simple MSBuild properties with one backup."""
    unknown = set(edits) - set(EDITABLE_PROJECT_PROPERTIES)
    if unknown:
        raise ValueError(f"Unsupported project properties: {', '.join(sorted(unknown))}")
    model = read_project_file(path)
    ambiguous = model.get("ambiguousProperties", {})
    blocked = sorted(name for name in edits if name in ambiguous)
    if blocked:
        details = "; ".join(f"{name}: {ambiguous[name]}" for name in blocked)
        raise ValueError(
            "Lexeditor cannot safely edit conditional or multiply-defined MSBuild properties without evaluating MSBuild: "
            + details
        )

    raw = path.read_text(encoding="utf-8-sig")
    candidate = raw
    saved = 0

    for name, incoming in edits.items():
        value = str(incoming).strip()
        if not value:
            raise ValueError(f"{name} cannot be empty")
        escaped = html.escape(value, quote=False)
        pattern = re.compile(
            rf"(<{re.escape(name)}(?:\s+[^>]*)?>)(.*?)(</{re.escape(name)}>)",
            re.IGNORECASE | re.DOTALL,
        )
        masked = _mask_xml_non_markup(candidate)
        matches = list(pattern.finditer(masked))
        parsed_count = sum(1 for row in model.get("propertyRows", []) if row.get("name") == name)
        if parsed_count and len(matches) != parsed_count:
            raise ValueError(
                f"Cannot safely patch {name}: textual MSBuild spans do not match parsed property definitions"
            )
        match = matches[0] if matches else None
        if match:
            current = html.unescape(candidate[match.start(2):match.end(2)].strip())
            if current == value:
                continue
            candidate = (
                candidate[:match.start(2)]
                + escaped
                + candidate[match.end(2):]
            )
            saved += 1
            continue

        parsed = ET.fromstring(candidate)
        unconditional_groups = [
            group
            for group in parsed
            if _local_name(group.tag) == "PropertyGroup" and not group.attrib.get("Condition", "").strip()
        ]
        if not unconditional_groups:
            raise ValueError(
                f"Cannot add {name}: MSBuild project has no unconditional PropertyGroup"
            )
        # Use textual bounds for the first unconditional PropertyGroup so comments/formatting remain intact.
        property_group_pattern = re.compile(
            r"<PropertyGroup(?P<attrs>\s+[^>]*)?>.*?</PropertyGroup\s*>",
            re.IGNORECASE | re.DOTALL,
        )
        group = None
        masked = _mask_xml_non_markup(candidate)
        parsed_groups = [group for group in parsed if _local_name(group.tag) == "PropertyGroup"]
        textual_groups = list(property_group_pattern.finditer(masked))
        if len(textual_groups) != len(parsed_groups):
            raise ValueError(
                f"Cannot add {name}: textual PropertyGroup spans do not match parsed MSBuild groups"
            )
        for candidate_group in textual_groups:
            opening = candidate[candidate_group.start():candidate_group.end()].split(">", 1)[0]
            if re.search(r"\bCondition\s*=", opening, re.IGNORECASE):
                continue
            group = candidate_group
            break
        if group is None:
            raise ValueError(
                f"Cannot add {name}: could not locate an unconditional PropertyGroup text span"
            )
        close = re.search(r"</PropertyGroup\s*>", group.group(0), re.IGNORECASE)
        close_at = group.start() + close.start()
        line_start = candidate.rfind("\n", 0, close_at) + 1
        indentation = re.match(r"\s*", candidate[line_start:close_at]).group(0)
        insertion = f"{indentation}  <{name}>{escaped}</{name}>\n"
        candidate = candidate[:close_at] + insertion + candidate[close_at:]
        saved += 1

    backup = path.with_name(path.name + ".lexeditor.bak")
    if saved:
        ET.fromstring(candidate)
        clear_write_helper(backup)
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        clear_write_helper(temporary)
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    return {
        "saved": saved,
        "backup": str(backup) if saved else "",
        "project": read_project_file(path),
    }


def _safe_project_path(project: Path, requested: str) -> Path:
    relative = Path(str(requested).replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Source path must be relative to the selected project")
    root = project.resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Source path escaped the selected project")
    if not target.is_file():
        raise FileNotFoundError(target)
    if target.suffix.casefold() not in _TEXT_SUFFIXES:
        raise ValueError(f"Unsupported source file type: {target.suffix or '(none)'}")
    if target.stat().st_size > 2_000_000:
        raise ValueError("Source file is too large for the source-only editor")
    return target


def _decode_source(raw: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("Source file is not supported text")


def read_source(project: Path, requested: str) -> dict:
    target = _safe_project_path(project, requested)
    text, encoding = _decode_source(target.read_bytes())
    return {
        "path": target.relative_to(project.resolve()).as_posix(),
        "absolutePath": str(target),
        "encoding": encoding,
        "text": text,
        "size": target.stat().st_size,
    }


def save_source(project: Path, requested: str, text: str) -> dict:
    target = _safe_project_path(project, requested)
    _old_text, encoding = _decode_source(target.read_bytes())
    candidate = str(text)
    if target.suffix.casefold() in {".xml", ".csproj", ".props", ".targets"}:
        try:
            ET.fromstring(candidate)
        except ET.ParseError as error:
            raise ValueError(f"XML is not well formed: {error}") from error
    backup = target.with_name(target.name + ".lexeditor.bak")
    clear_write_helper(backup)
    shutil.copy2(target, backup)
    temporary = target.with_name(target.name + ".lexeditor.tmp")
    clear_write_helper(temporary)
    temporary.write_text(candidate, encoding=encoding)
    temporary.replace(target)
    result = read_source(project, requested)
    result.update({"saved": 1, "backup": str(backup)})
    return result


def _selected_game_root(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return Path(explicit).resolve()
    configured = os.environ.get("LEXEDITOR_BANNERLORD_ROOT", "").strip()
    return Path(configured).resolve() if configured else None


def _build_path_overrides(project: Path, selected_game: Path) -> dict[str, str]:
    descriptor = contained_project_path(project, "SubModule.xml", require_file=True)
    module_id = str(read_submodule(descriptor).get("id") or "").strip()
    if not module_id or not _MODULE_ID.fullmatch(module_id):
        raise ValueError(f"Bannerlord project has an unsafe module Id: {module_id or '(missing)'}")

    selected_game = selected_game.resolve()
    game_bin = (selected_game / "bin" / "Win64_Shipping_Client").resolve()
    modules_root = (selected_game / "Modules").resolve()
    module_dir = (modules_root / module_id).resolve()
    if modules_root not in module_dir.parents:
        raise ValueError("Resolved Bannerlord build module path escaped the Modules folder")
    output_path = (module_dir / "bin" / "Win64_Shipping_Client").resolve()
    if module_dir not in output_path.parents:
        raise ValueError("Resolved Bannerlord build output path escaped the module folder")

    return {
        "BannerlordDir": str(selected_game),
        "GameBin": str(game_bin),
        "ModuleDir": str(module_dir),
        "OutputPath": str(output_path) + os.sep,
    }


def run_build(
    project: Path,
    requested: str | None = None,
    configuration: str = "Debug",
    timeout: int = 300,
    game_root: Path | None = None,
) -> dict:
    """Run dotnet directly and pin build/deploy paths to Lexeditor's selected install."""
    configuration = str(configuration or "Debug")
    if configuration not in {"Debug", "Release"}:
        raise ValueError("Configuration must be Debug or Release")
    project_file = _resolve_project_file(project, requested)
    selected_game = _selected_game_root(game_root)
    command = [
        "dotnet",
        "build",
        str(project_file),
        "--configuration",
        configuration,
        "--nologo",
    ]
    path_overrides: dict[str, str] = {}
    if selected_game is not None:
        # These global properties override project-local values. Pin all standard
        # Bannerlord write/reference roots used by Lexeditor projects, not only
        # BannerlordDir, so a stale or edited ModuleDir/OutputPath cannot redirect
        # build output or AfterTargets deployment away from the selected install.
        path_overrides = _build_path_overrides(project, selected_game)
        command.extend(f"-p:{name}={value}" for name, value in path_overrides.items())
    try:
        completed = subprocess.run(
            command,
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise RuntimeError("dotnet was not found on PATH") from error
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        raise RuntimeError(
            "dotnet build exceeded the 300 second safety timeout.\n"
            + str(stdout)[-8000:] + "\n" + str(stderr)[-8000:]
        ) from error
    output = ((completed.stdout or "") + (completed.stderr or ""))[-500_000:]
    return {
        "returnCode": completed.returncode,
        "succeeded": completed.returncode == 0,
        "configuration": configuration,
        "project": project_file.name,
        "command": command,
        "gameRootOverride": str(selected_game) if selected_game is not None else "",
        "pathOverrides": path_overrides,
        "output": output,
    }
