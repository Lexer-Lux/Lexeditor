"""Safe structured editing for documented Warband Module System record lists.

The parser never imports or executes mod source. It locates the documented
top-level record list and patches only selected field spans, preserving every
other byte of the source file.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading

_LOCK = threading.Lock()


def _f(key, label, kind="expr", help="", **extra):
    value = {"key": key, "label": label, "kind": kind, "help": help}
    value.update(extra)
    return value


SCHEMAS = {
    "skills": {
        "label": "Skills", "filename": "module_skills.py", "variable": "skills",
        "status": "partial",
        "notes": "Names, maximum levels and descriptions have semantic controls. Skill flags remain a validated Module System expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable skl_* source identity. Renaming is disabled because other Module System files reference it."),
            _f("name", "Name", "string", "Player-facing skill name."),
            _f("flags", "Flags", "expr", "sf_* governing-attribute, party-effect and inactive flags. Preserved as a validated expression."),
            _f("maxLevel", "Maximum level", "integer", "Highest level the skill can reach.", min=0),
            _f("description", "Description", "text", "Player-facing skill description."),
        ],
        "columns": ["name", "id", "maxLevel"],
    },
    "quests": {
        "label": "Quests", "filename": "module_quests.py", "variable": "quests",
        "status": "partial",
        "notes": "Quest names and descriptions have semantic controls. Quest flags remain a validated Module System expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable qst_* source identity. References are not rewritten."),
            _f("name", "Name", "string", "Name shown in the quest screen."),
            _f("flags", "Flags", "expr", "qf_* quest behavior flags, preserved as a validated expression."),
            _f("description", "Description", "text", "Quest description compiled for the player."),
        ],
        "columns": ["name", "id", "flags"],
    },
    "strings": {
        "label": "Strings", "filename": "module_strings.py", "variable": "strings",
        "status": "integrated",
        "notes": "The complete documented (id, text) record is editable; IDs stay fixed so references remain valid.",
        "fields": [
            _f("id", "ID", "identity", "Stable str_* source identity. References are not rewritten."),
            _f("value", "Text", "text", "Reusable localized text compiled by the Module System."),
        ],
        "columns": ["id", "value"],
    },
    "info-pages": {
        "label": "Info pages", "filename": "module_info_pages.py", "variable": "info_pages",
        "status": "integrated",
        "notes": "The complete documented (id, name, text) source record is editable; installed compiled manuals remain read-only.",
        "fields": [
            _f("id", "ID", "identity", "Stable ip_* source identity. References are not rewritten."),
            _f("name", "Name", "string", "Name displayed in Warband's information page list."),
            _f("text", "Text", "text", "Body displayed on the information page."),
        ],
        "columns": ["name", "id", "text"],
    },
    "music": {
        "label": "Music", "filename": "module_music.py", "variable": "tracks",
        "status": "partial",
        "notes": "Track filenames are structured. Playback and continue masks remain validated mtf_* expressions.",
        "fields": [
            _f("id", "ID", "identity", "Stable track identity."),
            _f("file", "Audio file", "string", "Filename of the music track."),
            _f("flags", "Playback flags", "expr", "mtf_* situations/cultures in which the track may start."),
            _f("continueFlags", "Continue flags", "expr", "mtf_* situations/cultures in which the track may continue."),
        ],
        "columns": ["id", "file", "flags"],
    },
    "sounds": {
        "label": "Sounds", "filename": "module_sounds.py", "variable": "sounds",
        "status": "partial",
        "notes": "Sound event identities and flags are structured. The variable sample-list expression remains source syntax because entries may carry per-sample flags.",
        "fields": [
            _f("id", "ID", "identity", "Stable snd_* source identity."),
            _f("flags", "Flags", "expr", "sf_* sound-event flags, preserved as a validated expression."),
            _f("samples", "Samples", "expr", "Sample list. Entries may be filenames or filename/flag pairs."),
        ],
        "columns": ["id", "flags", "samples"],
    },
    "meshes": {
        "label": "Meshes", "filename": "module_meshes.py", "variable": "meshes",
        "status": "partial",
        "notes": "Resource name and all nine documented transform values have semantic controls. Mesh flags remain a validated expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable mesh_* source identity."),
            _f("flags", "Flags", "expr", "header_meshes.py flags, preserved as a validated expression."),
            _f("resource", "Resource name", "string", "BRF mesh resource name."),
            _f("translateX", "Translate X", "number", "Automatic X-axis translation."),
            _f("translateY", "Translate Y", "number", "Automatic Y-axis translation."),
            _f("translateZ", "Translate Z", "number", "Automatic Z-axis translation."),
            _f("rotateX", "Rotate X", "number", "Automatic rotation angle around X."),
            _f("rotateY", "Rotate Y", "number", "Automatic rotation angle around Y."),
            _f("rotateZ", "Rotate Z", "number", "Automatic rotation angle around Z."),
            _f("scaleX", "Scale X", "number", "Automatic X scale."),
            _f("scaleY", "Scale Y", "number", "Automatic Y scale."),
            _f("scaleZ", "Scale Z", "number", "Automatic Z scale."),
        ],
        "columns": ["id", "resource", "scaleX"],
    },
    "factions": {
        "label": "Factions", "filename": "module_factions.py", "variable": "factions",
        "status": "partial", "minFields": 6, "maxFields": 7,
        "notes": "Names and coherence are semantic. Flags, relation/rank lists and optional color remain validated source expressions; reference IDs stay fixed.",
        "fields": [
            _f("id", "ID", "identity", "Stable fac_* source identity."),
            _f("name", "Name", "string", "Faction display name."),
            _f("flags", "Flags", "expr", "Faction rating/behavior expression."),
            _f("coherence", "Coherence", "number", "Self-relation/coherence value exported by process_factions.py."),
            _f("relations", "Relations", "expr", "List of (faction id, relation) pairs."),
            _f("ranks", "Ranks", "expr", "Faction rank-name list."),
            _f("color", "Color", "expr", "Optional faction color expression.", optional=True),
        ],
        "columns": ["name", "id", "coherence"],
    },
    "postfx": {
        "label": "Post-processing", "filename": "module_postfx.py", "variable": "postfx_params",
        "status": "partial",
        "notes": "Tonemap operator and the three documented four-value shader vectors have bounded/semantic controls. Flags remain a validated expression.",
        "fields": [
            _f("id", "ID", "identity", "Stable pfx_* source identity."),
            _f("flags", "Flags", "expr", "Post-processing flags from header_postfx.py."),
            _f("tonemap", "Tonemap operator", "integer", "Documented operator type 0, 1, 2 or 3.", min=0, max=3),
            _f("params1", "HDR parameters", "vec4", "HDR range, exposure scaler, luminance-average scaler, luminance-max scaler.",
               components=["HDR range", "Exposure", "Luminance average", "Luminance max"]),
            _f("params2", "Bloom / blur", "vec4", "Brightpass threshold, post power, blur strength, blur amount.",
               components=["Brightpass threshold", "Post power", "Blur strength", "Blur amount"]),
            _f("params3", "Lighting coefficients", "vec4", "Ambient, sun and specular coefficients plus reserved value.",
               components=["Ambient", "Sun", "Specular", "Reserved"]),
        ],
        "columns": ["id", "tonemap", "flags"],
    },
}

SCHEMA_BY_FILENAME = {schema["filename"]: key for key, schema in SCHEMAS.items()}


def _source(path: Path):
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp1254", "latin1"):
        try:
            return raw.decode(encoding), encoding, raw
        except UnicodeDecodeError:
            pass
    return raw.decode("latin1"), "latin1", raw


def _skip_string(text: str, index: int) -> int:
    quote = text[index]
    triple = text.startswith(quote * 3, index)
    delimiter = quote * (3 if triple else 1)
    cursor = index + len(delimiter)
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text.startswith(delimiter, cursor):
            return cursor + len(delimiter)
        cursor += 1
    raise ValueError("Unterminated Python string in Module System source")


def _list_start(text: str, variable: str) -> int:
    match = re.search(r"(?m)^[ \t]*" + re.escape(variable) + r"[ \t]*=[ \t]*\[", text)
    if not match:
        raise ValueError(f"Source does not contain {variable} = [...]")
    return text.find("[", match.start(), match.end())


def _record_spans(text: str, variable: str):
    outer = _list_start(text, variable)
    stack = ["["]
    spans = []
    start = None
    pairs = {")": "(", "]": "[", "}": "{"}
    cursor = outer + 1
    while cursor < len(text):
        char = text[cursor]
        if char in "'\"":
            cursor = _skip_string(text, cursor)
            continue
        if char == "#":
            newline = text.find("\n", cursor)
            cursor = len(text) if newline < 0 else newline + 1
            continue
        if char in "([{":
            if len(stack) == 1:
                start = cursor
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                raise ValueError(f"Unbalanced {variable} record list")
            stack.pop()
            if len(stack) == 1 and start is not None:
                spans.append((start, cursor + 1))
                start = None
            elif not stack:
                return spans
        cursor += 1
    raise ValueError(f"Unterminated {variable} record list")


def _split_fields(text: str, start: int, end: int):
    fields = []
    stack = []
    pairs = {")": "(", "]": "[", "}": "{"}
    cursor = start + 1
    field_start = cursor
    while cursor < end - 1:
        char = text[cursor]
        if char in "'\"":
            cursor = _skip_string(text, cursor)
            continue
        if char == "#":
            newline = text.find("\n", cursor, end)
            cursor = end - 1 if newline < 0 else newline + 1
            continue
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack[-1] != pairs[char]:
                raise ValueError("Unbalanced record expression")
            stack.pop()
        elif char == "," and not stack:
            left, right = field_start, cursor
            while left < right and text[left].isspace():
                left += 1
            while right > left and text[right - 1].isspace():
                right -= 1
            if left < right:
                fields.append((left, right))
            field_start = cursor + 1
        cursor += 1
    left, right = field_start, end - 1
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if left < right:
        fields.append((left, right))
    if stack:
        raise ValueError("Unbalanced record expression")
    return fields


def _decode(expression: str, field: dict):
    kind = field["kind"]
    if kind in {"identity", "string", "text"}:
        value = ast.literal_eval(expression)
        if not isinstance(value, str):
            raise ValueError("expected a string literal")
        return value
    if kind == "integer":
        value = ast.literal_eval(expression)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("expected an integer literal")
        return value
    if kind == "number":
        value = ast.literal_eval(expression)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("expected a finite numeric literal")
        return value
    if kind == "vec4":
        value = ast.literal_eval(expression)
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            raise ValueError("expected four numeric values")
        result = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
                raise ValueError("expected four finite numeric values")
            result.append(item)
        return result
    return expression.strip()


def _records(text: str, schema: dict):
    specs = schema["fields"]
    minimum = int(schema.get("minFields", len(specs)))
    maximum = int(schema.get("maxFields", len(specs)))
    rows = []
    for record_index, (start, end) in enumerate(_record_spans(text, schema["variable"])):
        spans = _split_fields(text, start, end)
        line = text.count("\n", 0, start) + 1
        raw_fields = [text[a:b] for a, b in spans]
        row = {"recordIndex": record_index, "line": line, "_spans": spans, "fields": {},
               "rawFields": {}, "fieldProblems": {}, "presentFields": []}
        if not minimum <= len(spans) <= maximum:
            row["id"] = f"record@{line}"
            row["name"] = row["id"]
            row["problem"] = (f"Expected {minimum}" + (f"-{maximum}" if maximum != minimum else "")
                              + f" fields; found {len(spans)}. Use source editing for this record.")
            rows.append(row)
            continue
        for index, spec in enumerate(specs):
            if index >= len(spans):
                continue
            key = spec["key"]
            expression = raw_fields[index]
            row["rawFields"][key] = expression
            row["presentFields"].append(key)
            try:
                row["fields"][key] = _decode(expression, spec)
            except Exception as error:
                row["fields"][key] = expression.strip()
                row["fieldProblems"][key] = str(error)
        identity = row["fields"].get("id")
        if not isinstance(identity, str):
            row["id"] = f"record@{line}"
            row["problem"] = "Record ID is not a string literal. Use source editing for this record."
        else:
            row["id"] = identity
        display = row["fields"].get("name")
        for key in ("file", "resource", "value"):
            if isinstance(display, str):
                break
            display = row["fields"].get(key)
        row["name"] = display if isinstance(display, str) else row["id"]
        rows.append(row)
    return rows


def _public_schema(schema: dict):
    return {key: value for key, value in schema.items() if key != "variable"}


def dataset_data(root, dataset: str):
    if dataset not in SCHEMAS:
        raise ValueError("Unknown Warband Module System dataset")
    root = Path(root)
    schema = SCHEMAS[dataset]
    path = root / schema["filename"]
    public = _public_schema(schema)
    if not path.is_file():
        return {"dataset": dataset, "available": False, "rows": [], "sha256": "", "schema": public}
    text, encoding, raw = _source(path)
    rows = _records(text, schema)
    seen = {}
    for row in rows:
        if row["id"].startswith("record@"):
            continue
        if row["id"] in seen:
            row["problem"] = f"Duplicate ID {row['id']!r}; repair source before structured editing."
            seen[row["id"]]["problem"] = row["problem"]
        else:
            seen[row["id"]] = row
    for row in rows:
        row.pop("_spans", None)
    return {"dataset": dataset, "available": True, "filename": schema["filename"],
            "encoding": encoding, "sha256": hashlib.sha256(raw).hexdigest(),
            "rows": rows, "schema": public}


def _expression(value):
    text = str(value).strip()
    if not text:
        raise ValueError("Expression cannot be empty")
    modern = re.sub(r"(?<=[0-9a-fA-F])L\b", "", text)
    ast.parse(modern, mode="eval")
    return text


def _encode(value, spec: dict):
    kind = spec["kind"]
    if kind in {"string", "text"}:
        return json.dumps(str(value), ensure_ascii=False)
    if kind == "identity":
        raise ValueError("Record IDs are fixed; edit references in source if an ID must change")
    if kind == "integer":
        if isinstance(value, bool):
            raise ValueError("Expected an integer")
        try:
            number = int(value)
            if float(value) != number:
                raise ValueError
        except Exception as error:
            raise ValueError("Expected an integer") from error
        if "min" in spec and number < spec["min"]:
            raise ValueError(f"{spec['label']} must be at least {spec['min']}")
        if "max" in spec and number > spec["max"]:
            raise ValueError(f"{spec['label']} must be at most {spec['max']}")
        return str(number)
    if kind == "number":
        try:
            number = float(value)
        except Exception as error:
            raise ValueError("Expected a number") from error
        if not math.isfinite(number):
            raise ValueError("Expected a finite number")
        if "min" in spec and number < spec["min"]:
            raise ValueError(f"{spec['label']} must be at least {spec['min']}")
        if "max" in spec and number > spec["max"]:
            raise ValueError(f"{spec['label']} must be at most {spec['max']}")
        return str(int(number)) if number.is_integer() else format(number, ".15g")
    if kind == "vec4":
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            raise ValueError(f"{spec['label']} needs four numbers")
        rendered = []
        for item in value:
            try:
                number = float(item)
            except Exception as error:
                raise ValueError(f"{spec['label']} needs four numbers") from error
            if not math.isfinite(number):
                raise ValueError(f"{spec['label']} needs finite numbers")
            rendered.append(str(int(number)) if number.is_integer() else format(number, ".15g"))
        return "[" + ", ".join(rendered) + "]"
    return _expression(value)


def _validate_python(encoded: bytes):
    python27 = Path(r"C:\Python27\python.exe")
    if not python27.is_file():
        return
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temporary:
        temporary.write(encoded)
        temporary_path = Path(temporary.name)
    try:
        check = subprocess.run(
            [str(python27), "-c", "import sys; compile(open(sys.argv[1],'rb').read(),sys.argv[1],'exec')", str(temporary_path)],
            capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if check.returncode:
            raise ValueError((check.stderr or check.stdout).decode("utf-8", errors="replace").strip())
    finally:
        temporary_path.unlink(missing_ok=True)


def save_dataset(root, dataset: str, expected_sha256: str, edits: list[dict]):
    if dataset not in SCHEMAS:
        raise ValueError("Unknown Warband Module System dataset")
    schema = SCHEMAS[dataset]
    path = Path(root) / schema["filename"]
    with _LOCK:
        text, encoding, raw = _source(path)
        current_sha = hashlib.sha256(raw).hexdigest()
        if current_sha != expected_sha256:
            raise ValueError(f"{schema['filename']} changed; reload before saving")
        records = _records(text, schema)
        identities = [row["id"] for row in records]
        if any(row.get("problem") for row in records):
            raise ValueError("Source contains records that require source repair before structured saving")
        if len(set(identities)) != len(identities):
            raise ValueError("Duplicate record IDs require source repair")
        if len({int(edit["recordIndex"]) for edit in edits}) != len(edits):
            raise ValueError("Send each record only once")
        specs = {field["key"]: field for field in schema["fields"]}
        patches = []
        changed_records = 0
        for edit in edits:
            index = int(edit["recordIndex"])
            if not 0 <= index < len(records):
                raise ValueError("Record no longer exists")
            row = records[index]
            if row["id"] != edit.get("originalId"):
                raise ValueError("Record identity changed; reload before saving")
            row_changed = False
            for key, value in (edit.get("fields") or {}).items():
                spec = specs.get(key)
                if spec is None or key == "id":
                    raise ValueError("Unknown or fixed Module System field")
                field_index = schema["fields"].index(spec)
                if field_index >= len(row["_spans"]):
                    raise ValueError(f"{spec['label']} is not present in this source record")
                replacement = _encode(value, spec)
                a, b = row["_spans"][field_index]
                if text[a:b] == replacement:
                    continue
                patches.append((a, b, replacement))
                row_changed = True
            changed_records += int(row_changed)
        if not patches:
            return {"saved": 0, "sha256": current_sha}
        candidate = text
        for a, b, replacement in sorted(patches, reverse=True):
            candidate = candidate[:a] + replacement + candidate[b:]
        reparsed = _records(candidate, schema)
        if len(reparsed) != len(records) or [row["id"] for row in reparsed] != identities:
            raise ValueError("Save changed record identities or record count")
        if [len(row["_spans"]) for row in reparsed] != [len(row["_spans"]) for row in records]:
            raise ValueError("Save changed Module System field structure")
        if any(ord(char) > 127 for char in candidate) and not re.search(
                r"coding[:=]\s*[-\w.]+", "\n".join(candidate.splitlines()[:2])):
            candidate = f"# coding: {encoding}\n" + candidate
        encoded = candidate.encode(encoding)
        _validate_python(encoded)
        if path.read_bytes() != raw:
            raise ValueError(f"{schema['filename']} changed while validating; reload before saving")
        backup = path.with_name(path.name + ".lexeditor.bak")
        backup.write_bytes(raw)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{path.stem}-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return {"saved": changed_records, "sha256": hashlib.sha256(encoded).hexdigest(), "backup": str(backup)}
