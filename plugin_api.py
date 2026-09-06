"""Small, stable contract between the Lexeditor shell and game plugins."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import os
from typing import Callable, Protocol


CheckFunction = Callable[[], list[str]]
LaunchFunction = Callable[[], int | None]
SmokeFunction = Callable[[], list[str]]
ProgressFunction = Callable[[int, int, str], None]
PrepareFunction = Callable[[Path, Path, ProgressFunction], object]
InitializeProjectFunction = Callable[[Path], None]


class PluginSession(Protocol):
    """One local plugin service that the shared desktop host supervises."""

    url: str

    def start(self) -> dict: ...
    def stop(self) -> None: ...


SessionFactory = Callable[..., PluginSession]


DiscoverProjectsFunction = Callable[[], list[Path]]
@dataclass(frozen=True)
class ModProjectSpec:
    """One game plugin's editable project boundary and creation template."""

    root_env: str
    default_root: Path
    required_paths: tuple[str, ...] = ()
    template_root: Path = Path()
    initialize: InitializeProjectFunction | None = None
    # Some games have more than one shape of editable thing. Warband has
    # Module System source projects and compiled installed modules, and a
    # root counts as valid when it satisfies any one group.
    required_any: tuple[tuple[str, ...], ...] = ()
    # Roots the plugin can find on disk, beyond the ones already chosen.
    discover: DiscoverProjectsFunction | None = None


@dataclass(frozen=True)
class GameInstallSpec:
    """Game files that the shared launcher can locate and validate."""

    root_env: str
    required_paths: tuple[str, ...]
    steam_app_id: str
    install_dir_names: tuple[str, ...]
    default_roots: tuple[Path, ...]
    data_env: str | None = None
    prepare: PrepareFunction | None = None
    prepare_on_scan: bool = False
    # The executable Lexeditor starts. Without this the shell picks the first
    # .exe in required_paths, which for some games is a third-party launcher
    # that runs its own updater. Lexeditor pins helper versions, so it starts
    # the game directly and keeps that decision.
    launch_path: str = ""


@dataclass(frozen=True)
class PluginFont:
    """One downloadable game-font dependency with a pinned source artifact."""

    font_id: str
    name: str
    destination: Path
    source_url: str
    sha256: str
    file_format: str
    alternatives: tuple[Path, ...] = ()


@dataclass(frozen=True)
class GitHubRepository:
    """One owner-only issue tracker associated with a game plugin."""

    full_name: str
    authorized_logins: tuple[str, ...]


HelperStatus = Callable[[], dict]
HelperInstall = Callable[[], dict]


@dataclass(frozen=True)
class GamePlugin:
    """One game integration discovered by the Lexeditor shell."""

    plugin_id: str
    name: str
    subtitle: str
    description: str
    accent: str
    check: CheckFunction
    launch: LaunchFunction
    smoke: SmokeFunction | None = None
    session_factory: SessionFactory | None = None
    fonts: tuple[PluginFont, ...] = ()
    installation: GameInstallSpec | None = None
    github: GitHubRepository | None = None
    projects: ModProjectSpec | None = None
    cover_art: Path | None = None
    # A plugin that drives a real game through a runtime helper cannot open
    # without it. `helper` names it and returns its status, so the Home screen
    # can report BROKEN rather than letting the editor open onto nothing.
    helper_name: str = ""
    helper_status: HelperStatus | None = None
    helper_install: HelperInstall | None = None
    # Lexeditor pins every helper and forbids self-updating, so a new upstream
    # release is something Lexer looks at and decides about. This reports the
    # newest published release without installing anything; the Home screen's
    # helper-versions panel is the one place that update path exists.
    helper_upstream: HelperStatus | None = None
    # Executable names this game runs as. The shell uses them so a game it did
    # not start itself is still reported as running, and can still be stopped.
    process_names: tuple[str, ...] = ()


def validate_plugin(plugin: GamePlugin) -> None:
    """Reject incomplete or unsafe descriptors at discovery time."""
    if not plugin.plugin_id or not plugin.plugin_id.replace("-", "").isalnum():
        raise ValueError("plugin_id must contain letters, numbers, or hyphens")
    for field in (plugin.name, plugin.subtitle, plugin.description, plugin.accent):
        if not field:
            raise ValueError(f"{plugin.plugin_id} has an empty descriptor field")
    if plugin.cover_art is not None:
        if (not plugin.cover_art.is_absolute() or not plugin.cover_art.is_file()
                or plugin.cover_art.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp", ".svg"}):
            raise ValueError(f"{plugin.plugin_id} has invalid packaged cover art")
    if plugin.installation is not None:
        spec = plugin.installation
        if not spec.root_env or not spec.required_paths or not spec.install_dir_names:
            raise ValueError(f"{plugin.plugin_id} has an incomplete installation descriptor")
        if not spec.steam_app_id.isdigit():
            raise ValueError(f"{plugin.plugin_id} has an invalid Steam application ID")
        for relative in spec.required_paths:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{plugin.plugin_id} has an unsafe required path: {relative}")
        if any(not path.is_absolute() and not (os.name != "nt" and PureWindowsPath(str(path)).is_absolute()) for path in spec.default_roots):
            raise ValueError(f"{plugin.plugin_id} has a relative default game path")
    font_ids: set[str] = set()
    destinations: set[Path] = set()
    for font in plugin.fonts:
        if not font.font_id or not font.font_id.replace("-", "").isalnum():
            raise ValueError(f"{plugin.plugin_id} has an invalid font id: {font.font_id}")
        if font.font_id in font_ids:
            raise ValueError(f"{plugin.plugin_id} has a duplicate font id: {font.font_id}")
        if not font.name or not font.destination.is_absolute():
            raise ValueError(f"{plugin.plugin_id}/{font.font_id} has an invalid name or destination")
        if font.destination in destinations:
            raise ValueError(f"{plugin.plugin_id} has duplicate font destination: {font.destination}")
        if not font.source_url.startswith("https://"):
            raise ValueError(f"{plugin.plugin_id}/{font.font_id} must use HTTPS")
        if len(font.sha256) != 64 or any(character not in "0123456789abcdef" for character in font.sha256.casefold()):
            raise ValueError(f"{plugin.plugin_id}/{font.font_id} has an invalid SHA-256")
        if font.file_format not in {"otf", "ttf", "woff", "woff2"}:
            raise ValueError(f"{plugin.plugin_id}/{font.font_id} has an invalid format")
        if any(not path.is_absolute() for path in font.alternatives):
            raise ValueError(f"{plugin.plugin_id}/{font.font_id} has a relative alternative path")
        font_ids.add(font.font_id)
        destinations.add(font.destination)
    if plugin.github is not None:
        repository = plugin.github
        parts = repository.full_name.split("/")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._")
        if (len(parts) != 2 or not all(parts) or
                any(character not in allowed for part in parts for character in part)):
            raise ValueError(f"{plugin.plugin_id} has an invalid GitHub repository")
        if not repository.authorized_logins or any(
                not login or any(character not in allowed for character in login)
                for login in repository.authorized_logins
        ):
            raise ValueError(f"{plugin.plugin_id} has invalid authorized GitHub logins")
    if plugin.projects is not None:
        projects = plugin.projects
        if not projects.root_env or not projects.default_root.is_absolute():
            raise ValueError(f"{plugin.plugin_id} has an invalid project descriptor")
        if projects.template_root and not projects.template_root.is_absolute():
            raise ValueError(f"{plugin.plugin_id} has a relative project template")
        for relative in projects.required_paths:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{plugin.plugin_id} has an unsafe required project path: {relative}")
