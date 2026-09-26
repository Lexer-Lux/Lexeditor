"""Terraria plugin lifecycle targeting tModLoader's native source workflow."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from core.plugin_api import GameInstallSpec, GamePlugin, ModProjectSpec
from core.plugin_manifest import install_spec, plugin_defaults, project_spec
from core.service_session import LocalPluginSession
from .runtime import inspect_runtime


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parent
TEMPLATE_ROOT = PLUGIN_ROOT / "template"


def _documents_folder() -> Path:
    """Windows' own Documents folder, which is not always under the profile.

    On this machine it is D:\\Documents, so a plugin that assumed
    `Path.home() / "Documents"` looked in a folder tModLoader never writes to,
    and then reported "no mod source" while the reader's own mod sources sat on
    another drive.
    """
    # One implementation for the whole program: the shared helper sets the
    # argument types on the Windows call, and a second copy of the call with
    # its own pointer type fails once those types are set.
    from core.mod_library import documents_folder
    try:
        return documents_folder()
    except (OSError, RuntimeError):
        return Path.home() / "Documents"


TERRARIA_SAVE_ROOT = Path(os.environ.get(
    "LEXEDITOR_TERRARIA_SAVE_ROOT",
    str(_documents_folder() / "My Games" / "Terraria"),
))
# tModLoader keeps ModSources beside the tModLoader save folder; the older
# ModLoader build kept "Mod Sources" with a space. A reader may have either, so
# both are searched and the one that exists is the default.
MOD_SOURCE_ROOTS = (
    TERRARIA_SAVE_ROOT / "tModLoader" / "ModSources",
    TERRARIA_SAVE_ROOT / "ModLoader" / "Mod Sources",
)
TMODLOADER_SAVE_ROOT = TERRARIA_SAVE_ROOT / "tModLoader"
MOD_SOURCES_ROOT = next((path for path in MOD_SOURCE_ROOTS if path.is_dir()),
                        MOD_SOURCE_ROOTS[0])
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


def _is_fresh_template_copy(root: Path) -> bool:
    """Recognize only Lexeditor's untouched packaged skeleton before rollback."""
    markers = (
        root / "build.txt",
        root / "LexeditorTerrariaMod.csproj",
        root / "LexeditorTerrariaMod.cs",
    )
    try:
        texts = [path.read_text(encoding="utf-8-sig") for path in markers]
    except OSError:
        return False
    return all("__LEXEDITOR_ID__" in text or "__LEXEDITOR_DISPLAY_NAME__" in text for text in texts)


def initialize_project(root: Path) -> None:
    """Turn the packaged skeleton into one valid tModLoader source project."""
    try:
        validate_mod_name(root.name)
    except ValueError:
        # Current shared ProjectManager copies the template before it calls the
        # initializer and no longer exposes a plugin validation hook. Roll back
        # only an untouched packaged skeleton so an invalid Terraria name does
        # not leave junk behind. Never remove an arbitrary existing project.
        if _is_fresh_template_copy(root):
            shutil.rmtree(root)
        raise
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
    found: list[Path] = []
    for root in MOD_SOURCE_ROOTS:
        if not root.is_dir():
            continue
        found.extend(path for path in root.iterdir()
                     if path.is_dir() and _looks_like_source_mod(path))
    return sorted(dict.fromkeys(found), key=lambda value: value.name.casefold())


def check() -> list[str]:
    if os.name != "nt":
        return []
    root = Path(os.environ.get("LEXEDITOR_TERRARIA_ROOT", r"C:\Program Files (x86)\Steam\steamapps\common\tModLoader"))
    if not root.is_dir():
        return []
    runtime = inspect_runtime(root)
    return [] if runtime["runtimeSupported"] else [runtime["runtimeReason"]]


class TerrariaSession(LocalPluginSession):
    def __init__(self, extra_env: dict[str, str] | None = None):
        super().__init__(
            module="plugins.terraria.server",
            plugin_id="terraria",
            app_root=ROOT,
            check=check,
            port_env="LEXEDITOR_TERRARIA_PORT",
            extra_env=dict(extra_env or {}),
        )


def smoke() -> list[str]:
    """Exercise Terraria project creation without touching a game or user save root."""
    with tempfile.TemporaryDirectory(prefix="lexeditor-terraria-smoke-") as directory:
        project = Path(directory) / "LexeditorTerrariaSmoke"
        shutil.copytree(TEMPLATE_ROOT, project)
        initialize_project(project)
        expected = (
            project / "build.txt",
            project / "LexeditorTerrariaSmoke.csproj",
            project / "LexeditorTerrariaSmoke.cs",
            project / "Localization" / "en-US.hjson",
        )
        missing = [path.name for path in expected if not path.is_file()]
        if missing:
            raise RuntimeError("Terraria smoke project is incomplete: " + ", ".join(missing))
    return [
        "tModLoader source template initializes in an isolated temporary project",
        "smoke test leaves installed Terraria/tModLoader and user ModSources untouched",
    ]


def launch() -> int:
    from core.desktop_host import run_host
    return run_host({"terraria": PLUGIN}, "terraria")


PLUGIN = GamePlugin(
    **plugin_defaults(__file__),
    check=check,
    launch=launch,
    smoke=smoke,
    session_factory=TerrariaSession,
    projects=project_spec(__file__, default_root=DEFAULT_PROJECT_ROOT, initialize=initialize_project, discover=discover_projects),
    installation=install_spec(__file__),
)
