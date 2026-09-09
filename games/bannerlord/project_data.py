"""Bannerlord project, MSBuild, source, and build helpers."""

from __future__ import annotations

from pathlib import Path
import html
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET


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


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _project_files(project: Path) -> list[Path]:
    return sorted(path for path in project.glob("*.csproj") if path.is_file())


def primary_project_file(project: Path) -> Path | None:
    files = _project_files(project)
    return files[0] if files else None


def _resolve_project_file(project: Path, requested: str | None = None) -> Path:
    if requested:
        target = (project / requested).resolve()
        root = project.resolve()
        if target != root and root not in target.parents:
            raise ValueError("Project file must stay inside the selected Bannerlord project")
        if target.suffix.casefold() != ".csproj" or not target.is_file():
            raise FileNotFoundError(target)
        return target
    target = primary_project_file(project)
    if target is None:
        raise FileNotFoundError(f"No .csproj found in {project}")
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

    return {
        "path": str(path),
        "name": path.name,
        "sdk": root.attrib.get("Sdk", ""),
        "properties": properties,
        "propertyRows": property_rows,
        "editableProperties": list(EDITABLE_PROJECT_PROPERTIES),
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
        match = pattern.search(candidate)
        if match:
            current = html.unescape(match.group(2).strip())
            if current == value:
                continue
            candidate = (
                candidate[:match.start()]
                + match.group(1) + escaped + match.group(3)
                + candidate[match.end():]
            )
            saved += 1
            continue

        group = re.search(r"</PropertyGroup\s*>", candidate, re.IGNORECASE)
        if not group:
            raise ValueError("MSBuild project has no PropertyGroup for editable properties")
        line_start = candidate.rfind("\n", 0, group.start()) + 1
        indentation = re.match(r"\s*", candidate[line_start:group.start()]).group(0)
        insertion = f"{indentation}  <{name}>{escaped}</{name}>\n"
        candidate = candidate[:group.start()] + insertion + candidate[group.start():]
        saved += 1

    backup = path.with_name(path.name + ".lexeditor.bak")
    if saved:
        ET.fromstring(candidate)
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
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
    shutil.copy2(target, backup)
    temporary = target.with_name(target.name + ".lexeditor.tmp")
    temporary.write_text(candidate, encoding=encoding)
    temporary.replace(target)
    result = read_source(project, requested)
    result.update({"saved": 1, "backup": str(backup)})
    return result


def run_build(
    project: Path,
    requested: str | None = None,
    configuration: str = "Debug",
    timeout: int = 300,
) -> dict:
    """Run dotnet build directly, never through a shell."""
    configuration = str(configuration or "Debug")
    if configuration not in {"Debug", "Release"}:
        raise ValueError("Configuration must be Debug or Release")
    project_file = _resolve_project_file(project, requested)
    command = [
        "dotnet",
        "build",
        str(project_file),
        "--configuration",
        configuration,
        "--nologo",
    ]
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
        "output": output,
    }
