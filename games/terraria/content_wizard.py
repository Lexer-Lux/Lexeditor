"""Small high-level content scaffolds for Terraria/tModLoader source mods."""

from __future__ import annotations

import binascii
import re
import struct
import zlib
from pathlib import Path
import os
import tempfile

from .assets import create_asset
from .localization import apply_localization_changes
from .source_text import create_source


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CSHARP_KEYWORDS = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char", "checked",
    "class", "const", "continue", "decimal", "default", "delegate", "do", "double", "else",
    "enum", "event", "explicit", "extern", "false", "finally", "fixed", "float", "for", "foreach",
    "goto", "if", "implicit", "in", "int", "interface", "internal", "is", "lock", "long",
    "namespace", "new", "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "ref", "return", "sbyte", "sealed", "short", "sizeof",
    "stackalloc", "static", "string", "struct", "switch", "this", "throw", "true", "try",
    "typeof", "uint", "ulong", "unchecked", "unsafe", "ushort", "using", "virtual", "void",
    "volatile", "while",
})
UTF8_BOM = b"\xef\xbb\xbf"


def validate_content_name(name: object) -> str:
    if not isinstance(name, str):
        raise ValueError("Content name must be text")
    value = name.strip()
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError("Content name must be an ASCII C# identifier")
    if value in _CSHARP_KEYWORDS:
        raise ValueError(f"Content name cannot be the C# keyword {value}")
    return value


def _single_line(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    normalized = value.strip()
    if not normalized and not allow_empty:
        raise ValueError(f"{label} cannot be empty")
    if any(character in value for character in ("\r", "\n", "\x00")):
        raise ValueError(f"{label} must fit on one line")
    return normalized


def default_display_name(name: str) -> str:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", spaced)
    return spaced.replace("_", " ").strip() or name


def render_mod_item_source(mod_name: str, class_name: str) -> str:
    return (
        "using Terraria;\n"
        "using Terraria.ModLoader;\n\n"
        f"namespace {mod_name}.Content.Items;\n\n"
        f"public sealed class {class_name} : ModItem\n"
        "{\n"
        "    public override void SetDefaults()\n"
        "    {\n"
        "        Item.width = 20;\n"
        "        Item.height = 20;\n"
        "    }\n"
        "}\n"
    )


def render_mod_system_source(mod_name: str, class_name: str) -> str:
    return (
        "using Terraria.ModLoader;\n\n"
        f"namespace {mod_name}.Common.Systems;\n\n"
        f"public sealed class {class_name} : ModSystem\n"
        "{\n"
        "}\n"
    )


def render_mod_player_source(mod_name: str, class_name: str) -> str:
    return (
        "using Terraria.ModLoader;\n\n"
        f"namespace {mod_name}.Common.Players;\n\n"
        f"public sealed class {class_name} : ModPlayer\n"
        "{\n"
        "}\n"
    )


def _create_logic_type(root: Path, name: object, *, kind: str, folder: str, renderer) -> dict:
    project = Path(root).resolve()
    if not project.is_dir():
        raise ValueError("Terraria source project does not exist")
    mod_name = validate_content_name(project.name)
    class_name = validate_content_name(name)
    relative = f"Common/{folder}/{class_name}.cs"
    source = create_source(project, relative, renderer(mod_name, class_name))
    return {"kind": kind, "name": class_name, "source": source}


def create_mod_system(root: Path, name: object) -> dict:
    return _create_logic_type(root, name, kind="system", folder="Systems", renderer=render_mod_system_source)


def create_mod_player(root: Path, name: object) -> dict:
    return _create_logic_type(root, name, kind="player", folder="Players", renderer=render_mod_player_source)


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def placeholder_png(size: int = 16, height: int | None = None) -> bytes:
    """Generate a valid visible checker texture that is intentionally replaceable."""
    width = size
    height = width if height is None else height
    if width < 1 or width > 256 or height < 1 or height > 256:
        raise ValueError("Placeholder texture size is out of range")
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            bright = ((x // 4) + (y // 4)) % 2 == 0
            row.extend((255, 0 if bright else 64, 255, 255))
        rows.append(bytes(row))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + _png_chunk(b"IEND", b"")
    )


def _localization_target(project: Path) -> Path:
    return project / "Localization" / "en-US.hjson"


def _initial_localization(mod_name: str) -> str:
    return (
        "# tModLoader may add generated localization entries here after build/reload.\n"
        "Mods: {\n"
        f"\t{mod_name}: {{\n"
        "\t}\n"
        "}\n"
    )


def _atomic_replace(target: Path, data: bytes) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, prefix=".lexeditor-content-", delete=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def create_mod_item(
    root: Path,
    name: object,
    display_name: object = "",
    tooltip: object = "",
) -> dict:
    """Create a minimal ModItem, localization and placeholder texture together."""
    project = Path(root).resolve()
    if not project.is_dir():
        raise ValueError("Terraria source project does not exist")
    mod_name = validate_content_name(project.name)
    class_name = validate_content_name(name)
    display = _single_line(display_name, "Display name", allow_empty=True) or default_display_name(class_name)
    tooltip_value = _single_line(tooltip, "Tooltip", allow_empty=True)

    source_relative = f"Content/Items/{class_name}.cs"
    texture_relative = f"Content/Items/{class_name}.png"
    source_target = project / source_relative
    texture_target = project / texture_relative
    if source_target.exists():
        raise ValueError(f"C# source file already exists: {source_relative}")
    if texture_target.exists():
        raise ValueError(f"Asset file already exists: {texture_relative}")

    localization_target = _localization_target(project)
    localization_target.parent.mkdir(parents=True, exist_ok=True)
    localization_existed = localization_target.is_file()
    localization_original = localization_target.read_bytes() if localization_existed else b""
    if localization_existed:
        try:
            localization_text = localization_original.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("Localization/en-US.hjson is not UTF-8 text") from error
        had_bom = localization_original.startswith(UTF8_BOM)
    else:
        localization_text = _initial_localization(mod_name)
        had_bom = False

    creates: dict[str, str] = {
        f"Mods.{mod_name}.Items.{class_name}.DisplayName": display,
    }
    if tooltip_value:
        creates[f"Mods.{mod_name}.Items.{class_name}.Tooltip"] = tooltip_value
    changed_localization = apply_localization_changes(localization_text, {}, creates)
    localization_bytes = (UTF8_BOM if had_bom else b"") + changed_localization.encode("utf-8")

    created_source = False
    created_texture = False
    localization_written = False
    try:
        source_state = create_source(project, source_relative, render_mod_item_source(mod_name, class_name))
        created_source = True
        texture_state = create_asset(project, texture_relative, placeholder_png())
        created_texture = True
        if localization_existed:
            _atomic_replace(localization_target, localization_bytes)
        else:
            with localization_target.open("xb") as handle:
                handle.write(localization_bytes)
                handle.flush()
                os.fsync(handle.fileno())
        localization_written = True
    except Exception:
        if localization_written:
            if localization_existed:
                _atomic_replace(localization_target, localization_original)
            else:
                localization_target.unlink(missing_ok=True)
        if created_texture:
            texture_target.unlink(missing_ok=True)
        if created_source:
            source_target.unlink(missing_ok=True)
        raise

    return {
        "kind": "item",
        "name": class_name,
        "source": source_state,
        "texture": texture_state,
        "localizationPath": localization_target.relative_to(project).as_posix(),
        "localizationKeys": list(creates),
        "displayName": display,
        "tooltip": tooltip_value,
    }
