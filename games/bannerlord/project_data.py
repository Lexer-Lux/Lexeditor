"""Inspect and safely edit Bannerlord C# project/source files."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from .paths import clear_write_helper, contained_project_path


_EDITABLE_PROPERTIES = {
    "TargetFramework",
    "AssemblyName",
    "RootNamespace",
    "LangVersion",
    "Nullable",
    "OutputPath",
    "AppendTargetFrameworkToOutputPath",
    "CopyLocalLockFileAssemblies",
    "BannerlordDir",
    "GameBin",
    "ModuleDir",
}


_XML_TEXT_MASK = re.compile(r"(?s)<!--.*?-->|<!\[CDATA\[.*?\]\]>")
_PROPERTY_GROUP = re.compile(
    r"(?is)<(?:[A-Za-z_][\w.-]*:)?PropertyGroup\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?:[A-Za-z_][\w.-]*:)?PropertyGroup\s*>"
)
_OPEN_PROPERTY_GROUP = re.compile(r"(?is)<(?:[A-Za-z_][\w.-]*:)?PropertyGroup\b(?P<attrs>[^>]*)>")
_CONDITION = re.compile(r"(?is)\bCondition\s*=")


def _mask_xml_text(text: str) -> str:
    return _XML_TEXT_MASK.sub(lambda match: " " * (match.end() - match.start()), text)


def _property_pattern(name: str) -> re.Pattern[str]:
    escaped = re.escape(name)
    return re.compile(
        rf"(?is)<(?P<prefix>[A-Za-z_][\w.-]*:)?{escaped}\b(?P<attrs>[^>]*)>(?P<value>.*?)</(?P=prefix){escaped}\s*>"
    )


def _unconditional_property_groups(text: str) -> list[tuple[int, int, str]]:
    masked = _mask_xml_text(text)
    groups = []
    for match in _PROPERTY_GROUP.finditer(masked):
        if _CONDITION.search(match.group("attrs") or ""):
            continue
        body_start = match.start("body")
        groups.append((body_start, match.end("body"), text[body_start:match.end("body")]))
    return groups


def _property_occurrences(text: str, name: str) -> list[dict]:
    """Return live property occurrences with group/element condition metadata."""
    masked = _mask_xml_text(text)
    result = []
    groups = list(_PROPERTY_GROUP.finditer(masked))
    for match in _property_pattern(name).finditer(masked):
        group = next((row for row in groups if row.start("body") <= match.start() < row.end("body")), None)
        if group is None:
            continue
        result.append(
            {
                "value": text[match.start("value"):match.end("value")],
                "span": match.span("value"),
                "elementCondition": bool(_CONDITION.search(match.group("attrs") or "")),
                "groupCondition": bool(_CONDITION.search(group.group("attrs") or "")),
            }
        )
    return result


def project_files(project: Path) -> list[Path]:
    root = Path(project).resolve()
    rows = []
    for candidate in sorted(root.glob("*.csproj"), key=lambda value: value.name.casefold()):
        try:
            safe = contained_project_path(root, candidate.name, require_file=True)
        except (ValueError, FileNotFoundError):
            continue
        rows.append(safe)
    return rows


def resolve_project_file(project: Path, requested: str | None = None) -> Path:
    files = project_files(project)
    if requested:
        candidate = contained_project_path(project, Path(str(requested)).name, require_file=True)
        if candidate.suffix.casefold() != ".csproj" or candidate.parent != Path(project).resolve():
            raise ValueError("Selected project must be a top-level .csproj file")
        if candidate not in files:
            raise ValueError(f"Unknown project file: {requested}")
        return candidate
    if not files:
        raise FileNotFoundError("No .csproj exists in this project")
    if len(files) > 1:
        raise ValueError("Several .csproj files exist; choose which one to build or edit")
    return files[0]


def primary_project_file(project: Path) -> Path | None:
    try:
        return resolve_project_file(project)
    except FileNotFoundError:
        return None


def _parse_project(path: Path) -> tuple[ET.ElementTree, ET.Element]:
    tree = ET.parse(path)
    root = tree.getroot()
    return tree, root


def _child_text(parent: ET.Element, name: str) -> str:
    for child in list(parent):
        if child.tag.rsplit("}", 1)[-1] == name:
            return (child.text or "").strip()
    return ""


def _tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def read_project_file(path: Path) -> dict:
    path = Path(path)
    tree, root = _parse_project(path)
    properties = {}
    property_rows = []
    ambiguous = {}
    text = path.read_text(encoding="utf-8-sig")
    for name in sorted(_EDITABLE_PROPERTIES):
        occurrences = _property_occurrences(text, name)
        if not occurrences:
            continue
        unconditional = [row for row in occurrences if not row["elementCondition"] and not row["groupCondition"]]
        editable = len(occurrences) == 1 and len(unconditional) == 1
        if editable:
            properties[name] = unconditional[0]["value"].strip()
        else:
            ambiguous[name] = (
                "multiple definitions" if len(occurrences) > 1 else "conditional definition"
            )
        for row in occurrences:
            property_rows.append(
                {
                    "name": name,
                    "value": row["value"].strip(),
                    "editable": editable and row is unconditional[0] if unconditional else False,
                    "conditioned": row["elementCondition"] or row["groupCondition"],
                }
            )
    sdk = root.attrib.get("Sdk", "")
    references = []
    packages = []
    items = []
    targets = []
    for element in root.iter():
        name = _tag_name(element)
        if name in {"Reference", "PackageReference", "Content", "None", "Compile"}:
            row = {"tag": name, "include": element.attrib.get("Include", ""), "metadata": {}}
            for child in list(element):
                row["metadata"][_tag_name(child)] = (child.text or "").strip()
            if name == "Reference":
                references.append(row)
            elif name == "PackageReference":
                packages.append(row)
            else:
                items.append(row)
        elif name == "Target":
            targets.append(
                {
                    "name": element.attrib.get("Name", ""),
                    "afterTargets": element.attrib.get("AfterTargets", ""),
                    "beforeTargets": element.attrib.get("BeforeTargets", ""),
                    "condition": element.attrib.get("Condition", ""),
                    "tasks": [_tag_name(child) for child in list(element)],
                }
            )
    return {
        "path": str(path),
        "name": path.name,
        "sdk": sdk,
        "properties": properties,
        "propertyRows": property_rows,
        "editableProperties": sorted(name for name in _EDITABLE_PROPERTIES if name not in ambiguous),
        "ambiguousProperties": ambiguous,
        "references": references,
        "packages": packages,
        "items": items,
        "targets": targets,
    }


def save_project_properties(path: Path, edits: dict) -> dict:
    path = Path(path)
    if path.suffix.casefold() != ".csproj":
        raise ValueError("Project settings can only edit .csproj files")
    unknown = set(edits) - _EDITABLE_PROPERTIES
    if unknown:
        raise ValueError(f"Unsupported MSBuild properties: {', '.join(sorted(unknown))}")
    original = path.read_text(encoding="utf-8-sig")
    candidate = original
    changed = set()
    for name, raw in edits.items():
        value = str(raw)
        occurrences = _property_occurrences(candidate, name)
        if occurrences:
            unconditional = [row for row in occurrences if not row["elementCondition"] and not row["groupCondition"]]
            if len(occurrences) != 1 or len(unconditional) != 1:
                raise ValueError(f"{name} is defined conditionally or more than once and is read-only")
            row = unconditional[0]
            old_value = candidate[row["span"][0]:row["span"][1]]
            if old_value == value:
                continue
            candidate = candidate[:row["span"][0]] + value + candidate[row["span"][1]:]
            changed.add(name)
            continue
        groups = _unconditional_property_groups(candidate)
        if not groups:
            raise ValueError(f"Cannot insert {name}: project has no unconditional PropertyGroup")
        _left, right, body = groups[0]
        line_start = candidate.rfind("\n", 0, right) + 1
        indent = re.match(r"[ \t]*", candidate[line_start:right]).group(0)
        child_indent = indent + "  "
        insertion = f"\n{child_indent}<{name}>{value}</{name}>"
        candidate = candidate[:right] + insertion + candidate[right:]
        changed.add(name)
    try:
        ET.fromstring(candidate)
    except ET.ParseError as error:
        raise ValueError(f"Saving project properties produced invalid XML: {error}") from error
    backup = path.with_name(path.name + ".lexeditor.bak")
    if changed:
        clear_write_helper(backup)
        shutil.copy2(path, backup)
        temporary = path.with_name(path.name + ".lexeditor.tmp")
        clear_write_helper(temporary)
        temporary.write_text(candidate, encoding="utf-8")
        temporary.replace(path)
    return {
        "saved": len(changed),
        "backup": str(backup) if changed else "",
        "project": read_project_file(path),
    }


def _safe_project_path(project: Path, requested: str) -> Path:
    if not requested:
        raise ValueError("Missing source path")
    return contained_project_path(project, *Path(requested).parts, require_file=True)


def _decode_source(raw: bytes) -> tuple[str, str]:
    # utf-8-sig also decodes ordinary UTF-8, so trying it first would classify
    # every UTF-8 file as BOM-bearing and add a BOM on the next write.
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    for encoding in ("utf-8", "cp1252"):
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


def save_source(
    project: Path,
    requested: str,
    text: str,
    original_text: str | None = None,
) -> dict:
    target = _safe_project_path(project, requested)
    current_text, encoding = _decode_source(target.read_bytes())
    if original_text is None:
        raise ValueError("Source save requires the originally loaded text; reload before saving")
    if current_text != str(original_text):
        raise ValueError("Source file changed on disk; reload before saving")
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
    # Write encoded bytes so Python's platform newline translation cannot
    # rewrite raw-source line endings on Windows. The selected codec still
    # preserves an existing UTF-8 BOM when one was present on load.
    temporary.write_bytes(candidate.encode(encoding))
    temporary.replace(target)
    result = read_source(project, requested)
    result.update({"saved": 1, "backup": str(backup)})
    return result


def _module_id(project: Path) -> str:
    descriptor = contained_project_path(project, "SubModule.xml", require_file=True)
    root = ET.parse(descriptor).getroot()
    element = root.find("Id")
    return "" if element is None else element.attrib.get("value", "")


def _contained_game_destination(
    game_root: Path,
    *parts: str,
    require_file: bool = False,
    require_dir: bool = False,
    allow_missing_leaf: bool = False,
) -> Path:
    from .paths import contained_game_path

    return contained_game_path(
        game_root,
        *parts,
        require_file=require_file,
        require_dir=require_dir,
        allow_missing_leaf=allow_missing_leaf,
    )


def run_build(
    project: Path,
    configuration: str = "Debug",
    game_root: Path | None = None,
    *,
    requested: str | None = None,
) -> dict:
    configuration = str(configuration).strip()
    if configuration not in {"Debug", "Release"}:
        raise ValueError("Build configuration must be Debug or Release")
    project_file = resolve_project_file(project, requested)
    command = ["dotnet", "build", str(project_file), "-c", configuration]
    module_id = _module_id(project)
    if game_root is None:
        value = os.environ.get("LEXEDITOR_BANNERLORD_ROOT", "").strip()
        game_root = Path(value) if value else None
    if game_root is not None:
        game_root = Path(game_root).resolve()
        modules_root = _contained_game_destination(game_root, "Modules", require_dir=True)
        game_bin = _contained_game_destination(game_root, "bin", "Win64_Shipping_Client", require_dir=True)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", module_id):
            raise ValueError("Unsafe module ID in SubModule.xml")
        module_root = _contained_game_destination(
            game_root,
            "Modules",
            module_id,
            allow_missing_leaf=True,
        )
        output_dir = module_root / "bin" / "Win64_Shipping_Client"
        if modules_root not in module_root.parents:
            raise ValueError("Module output escaped the selected Bannerlord Modules folder")
        command += [
            f"-p:BannerlordDir={game_root}",
            f"-p:GameBin={game_bin}",
            f"-p:ModuleDir={module_root}",
            f"-p:OutputPath={output_dir}{os.sep}",
            "-p:LexeditorSkipAssetDeploy=true",
        ]
    completed = subprocess.run(
        command,
        cwd=project,
        capture_output=True,
        text=True,
        shell=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return {
        "command": command,
        "returnCode": completed.returncode,
        "succeeded": completed.returncode == 0,
        "output": output,
        "project": project_file.name,
        "moduleId": module_id,
    }
