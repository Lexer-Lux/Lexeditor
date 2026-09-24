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
PrepareExistingProjectFunction = Callable[[Path], Path]


class PluginSession(Protocol):
    """One local plugin service that the shared desktop host supervises."""

    url: str

    def start(self) -> dict: ...
    def stop(self) -> None: ...


class GameProcessController(Protocol):
    """Optional game-specific launch/readiness contract; the shell owns its instance."""
    def launch(self, game_root: Path, project: Path) -> dict: ...
    def status(self) -> dict: ...
    def stop(self) -> dict: ...


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
    # Optional non-destructive normalization for an explicitly selected existing
    # project. It may return a managed copy while leaving the chosen source untouched.
    prepare_existing: PrepareExistingProjectFunction | None = None
    # Some games have more than one shape of editable thing. Warband has
    # Module System source projects and compiled installed modules, and a
    # root counts as valid when it satisfies any one group.
    required_any: tuple[tuple[str, ...], ...] = ()
    # Roots the plugin can find on disk, beyond the ones already chosen.
    discover: DiscoverProjectsFunction | None = None
    # What this game's loader actually recognises inside a mod folder, as
    # {category label: (suffix, ...)}. Adding a mod reports these counts so a
    # player can tell at a glance whether the folder was understood, instead of
    # finding out later that nothing loaded.
    content_types: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True)
class GameInstallSpec:
    """Game files that the shared launcher can locate and validate."""

    root_env: str
    required_paths: tuple[str, ...]
    steam_app_id: str
    install_dir_names: tuple[str, ...]
    default_roots: tuple[Path, ...]
    data_env: str | None = None
    # Steam artwork to show when the runtime's own capsule is the wrong game.
    # Terraria installs target the tModLoader loader, not Terraria itself.
    art_app_id: str | None = None
    prepare: PrepareFunction | None = None
    prepare_on_scan: bool = False
    # The executable Lexeditor starts. Without this the shell picks the first
    # .exe in required_paths, which for some games is a third-party launcher
    # that runs its own updater. Lexeditor pins helper versions, so it starts
    # the game directly and keeps that decision.
    launch_path: str = ""
    # Where a renderer wrapper - ReShade - has to sit for this game to load
    # it: the folder holding the executable that actually renders, relative to
    # the installation root. Declared per game and never guessed. Lexeditor
    # inferred it once from launch_path, wrote the DLL where nothing would
    # load it, and reported success.
    #
    # "" means the installation root, which is a statement, not a default: a
    # game whose renderer wrapper belongs somewhere else must say so.
    reshade_root: str = ""
    # The loader name ReShade goes in under for this game ("dxgi", "d3d9", ...).
    reshade_renderer: str = ""


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
    issue_label: str = ""


HelperStatus = Callable[[], dict]
HelperInstall = Callable[[], dict]


@dataclass(frozen=True)
class PluginHelper:
    """One independently versioned runtime/helper dependency for a plugin."""

    key: str
    name: str
    status: HelperStatus | None = None
    install: HelperInstall | None = None
    upstream: HelperStatus | None = None
    status_for_root: Callable[[Path | None], dict] | None = None
    install_for_root: Callable[[Path], dict] | None = None
    pinned: str = ""
    required: bool = True


@dataclass(frozen=True)
class GamePlugin:
    """One game integration discovered by the Lexeditor shell."""

    plugin_id: str
    name: str
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
    # False for a game Lexeditor must not start itself - one that only runs
    # properly through its store launcher. Play is then greyed out; Stop still
    # works on a copy the player started.
    can_launch: bool = True
    game_process_factory: Callable[[], GameProcessController] | None = None
    # Root-aware helper hooks prevent installing into an import-time default
    # after the user locates a different game folder. Legacy hooks remain valid.
    helper_status_for_root: Callable[[Path | None], dict] | None = None
    helper_install_for_root: Callable[[Path], dict] | None = None
    helper_pinned: str = ""
    # Named follow-up steps a helper's first-time setup can ask for, such as
    # purging a shader cache the helper cannot work with. The shell shows the
    # step beside the game with its button; it never runs one by itself.
    helper_actions: dict[str, Callable[[Path | None], dict]] | None = None
    # Explicit mod-loader adapter; editable project support alone is not proof
    # that imported packages can be enabled and removed in the game.
    mod_adapter: object | None = None
    # Does a mod built here actually load in the game? Stated by the plugin,
    # never inferred: an adapter that exists is not an adapter that works. The
    # developer page reads this, and the answer is no until someone proves
    # otherwise in the game itself.
    mods_load: bool = False
    managed_mod: object | None = None
    # Multi-helper plugins opt into independent setup/update rows. Legacy
    # singular fields above remain valid and are synthesized into one helper.
    helpers: tuple[PluginHelper, ...] = ()


def plugin_helpers(plugin: GamePlugin) -> tuple[PluginHelper, ...]:
    """Return normalized helpers without requiring legacy plugins to change."""
    if plugin.helpers:
        return plugin.helpers
    if not any((
        plugin.helper_name, plugin.helper_status, plugin.helper_install, plugin.helper_upstream,
        plugin.helper_status_for_root, plugin.helper_install_for_root, plugin.helper_pinned,
    )):
        return ()
    return (PluginHelper(
        key="default",
        name=plugin.helper_name or "Runtime helper",
        status=plugin.helper_status,
        install=plugin.helper_install,
        upstream=plugin.helper_upstream,
        status_for_root=plugin.helper_status_for_root,
        install_for_root=plugin.helper_install_for_root,
        pinned=plugin.helper_pinned,
    ),)


def _absolute_for_host_or_windows(path: Path) -> bool:
    """Accept native absolute paths plus Windows drive/UNC paths on non-Windows CI."""
    return path.is_absolute() or (os.name != "nt" and PureWindowsPath(str(path)).is_absolute())


def validate_plugin(plugin: GamePlugin) -> None:
    """Reject incomplete or unsafe descriptors at discovery time."""
    if not plugin.plugin_id or not plugin.plugin_id.replace("-", "").isalnum():
        raise ValueError("plugin_id must contain letters, numbers, or hyphens")
    for field in (plugin.name, plugin.accent):
        if not field:
            raise ValueError(f"{plugin.plugin_id} has an empty descriptor field")
    if plugin.helpers and any((
        plugin.helper_name, plugin.helper_status, plugin.helper_install, plugin.helper_upstream,
        plugin.helper_status_for_root, plugin.helper_install_for_root, plugin.helper_pinned,
    )):
        raise ValueError(f"{plugin.plugin_id} mixes legacy and multi-helper descriptors")
    helper_keys: set[str] = set()
    for helper in plugin_helpers(plugin):
        if (not helper.key or not helper.key.replace("-", "").isalnum()
                or helper.key in helper_keys or not helper.name):
            raise ValueError(f"{plugin.plugin_id} has an invalid or duplicate helper descriptor")
        if not (helper.status or helper.status_for_root):
            raise ValueError(f"{plugin.plugin_id}/{helper.key} has no helper status provider")
        if helper.install and helper.install_for_root:
            raise ValueError(f"{plugin.plugin_id}/{helper.key} declares two helper installers")
        helper_keys.add(helper.key)
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
        if spec.art_app_id is not None and not spec.art_app_id.isdigit():
            raise ValueError(f"{plugin.plugin_id} has an invalid Steam artwork ID")
        for relative in spec.required_paths:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{plugin.plugin_id} has an unsafe required path: {relative}")
        if any(not _absolute_for_host_or_windows(path) for path in spec.default_roots):
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
    if plugin.installation is not None:
        declared = plugin.installation.reshade_root
        if declared:
            path = Path(declared)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(
                    f"{plugin.plugin_id} has an unsafe ReShade folder: {declared}")
    if plugin.projects is not None:
        projects = plugin.projects
        if not projects.root_env or not _absolute_for_host_or_windows(projects.default_root):
            raise ValueError(f"{plugin.plugin_id} has an invalid project descriptor")
        if projects.template_root and not _absolute_for_host_or_windows(projects.template_root):
            raise ValueError(f"{plugin.plugin_id} has a relative project template")
        for relative in projects.required_paths:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{plugin.plugin_id} has an unsafe required project path: {relative}")
        for group in projects.required_any:
            if not group:
                raise ValueError(f"{plugin.plugin_id} has an empty project requirement group")
            for relative in group:
                path = Path(relative)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError(f"{plugin.plugin_id} has an unsafe alternate project path: {relative}")
