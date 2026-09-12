"""Terraria plugin lifecycle targeting tModLoader's native source workflow."""

from __future__ import annotations

import os
import re
from pathlib import Path

from plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from service_session import LocalPluginSession


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = PLUGIN_ROOT / "template"
TMODLOADER_SAVE_ROOT = Path(
    os.environ.get(
        "LEXEDITOR_TERRARIA_SAVE_ROOT",
        Path.home() / "Documents" / "My Games" / "Terraria" / "tModLoader",
    )
)
MOD_SOURCES_ROOT = TMODLOADER_SAVE_ROOT / "ModSources"
DEFAULT_PROJECT_ROOT = MOD_SOURCES_ROOT / "LexeditorTerrariaMod"


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
_TMODLOADER_RESERVED_NAMES = frozenset({"mod", "modloader", "tmodloader"})
_MOD_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_mod_name(name: str) -> None:
    """Enforce tModLoader's source-folder/internal-name boundary before mutation."""
    if not _MOD_IDENTIFIER.fullmatch(name):
        raise ValueError(
            "tModLoader mod names must be C# identifiers: start with a letter or underscore "
            "and use only ASCII letters, digits, or underscores"
        )
    if name in _CSHARP_KEYWORDS:
        raise ValueError(f"tModLoader mod name cannot be the C# keyword {name}")
    if name.casefold() in _TMODLOADER_RESERVED_NAMES:
        raise ValueError(f"tModLoader reserves the mod name {name}")


def initialize_project(root: Path) -> None:
    """Turn the packaged skeleton into one valid tModLoader source project."""
    validate_mod_name(root.name)
    mod_id = root.name
    replacements = {
        "__LEXEDITOR_DISPLAY_NAME__": root.name,
        "__LEXEDITOR_ID__": mod_id,
    }
    for filename in (
        "build.txt",
        "LexeditorTerrariaMod.csproj",
        "LexeditorTerrariaMod.cs",
        "Localization/en-US.hjson",
    ):
        path = root / filename
        text = path.read_text(encoding="utf-8-sig")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    for suffix in (".csproj", ".cs"):
        source = root / f"LexeditorTerrariaMod{suffix}"
        target = root / f"{mod_id}{suffix}"
        if source != target:
            source.replace(target)

    (root / "Content").mkdir(exist_ok=True)
    (root / "Localization").mkdir(exist_ok=True)


def _looks_like_source_mod(root: Path) -> bool:
    if not (root / "build.txt").is_file():
        return False
    return any(path.is_file() for path in root.glob("*.csproj"))


def discover_projects() -> list[Path]:
    if not MOD_SOURCES_ROOT.is_dir():
        return []
    return sorted(
        (path for path in MOD_SOURCES_ROOT.iterdir() if path.is_dir() and _looks_like_source_mod(path)),
        key=lambda value: value.name.casefold(),
    )


def check() -> list[str]:
    return []


class TerrariaSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(
            module="games.terraria.server",
            plugin_id="terraria",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_TERRARIA_PORT",
            extra_env=dict(extra_env or {}),
        )


def launch() -> int:
    from desktop_host import run_host
    return run_host({"terraria": PLUGIN}, "terraria")


PLUGIN = GamePlugin(
    plugin_id="terraria",
    name="Terraria",
    subtitle="tModLoader 1.4.4",
    description="Create and edit native tModLoader source mods without modifying vanilla Terraria.",
    accent="#77b255",
    check=check,
    launch=launch,
    session_factory=TerrariaSession,
    projects=ModProjectSpec(
        root_env="LEXEDITOR_TERRARIA_PROJECT",
        default_root=DEFAULT_PROJECT_ROOT,
        required_paths=("build.txt",),
        template_root=TEMPLATE_ROOT,
        initialize=initialize_project,
        validate_name=validate_mod_name,
        discover=discover_projects,
    ),
    installation=GameInstallSpec(
        root_env="LEXEDITOR_TERRARIA_ROOT",
        required_paths=("start-tModLoader.bat", "tModLoader.dll", "LaunchUtils"),
        steam_app_id="1281930",
        install_dir_names=("tModLoader",),
        default_roots=(Path(r"C:\Program Files (x86)\Steam\steamapps\common\tModLoader"),),
        launch_path="start-tModLoader.bat",
    ),
)
