"""What a game plugin *is*, as data; what integration code does, stays in code.

A plugin's descriptor used to be written out in full in `plugins/<id>/plugin.py`
mixed with its behaviour: the accent, the Steam application, where the game
installs, which of its programs is the game, and the lines shown while it
loads all sat between lambdas and a session class. That is two kinds of
information in one place, and the data half is the half a reader wants to see
at a glance.

`plugins/<id>/plugin.json` holds the data. `plugin.py` keeps the behaviour and
reads the manifest, so there is still exactly one source for each fact:

    from core.plugin_metadata import project_spec, plugin_defaults

    PLUGIN = GamePlugin(**plugin_defaults(__file__), check=check, launch=launch,
                        installation=install_spec(__file__),
                        projects=project_spec(__file__, default_root=paths.PROJECT_ROOT))

What does NOT belong here: anything this machine computes. The folder a
project is created in under the reader's Documents, downloaded cover art, and
the callables a plugin wires in are all worked out in Python, and the manifest
holds only what is the same on every machine.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from core.plugin_api import GameInstallSpec, ModProjectSpec

MANIFEST_NAME = "plugin.json"


@lru_cache(maxsize=None)
def manifest(plugin_file: str | Path) -> dict:
    """One plugin's `plugin.json`, read from beside its `plugin.py`."""
    path = Path(plugin_file).resolve().parent / MANIFEST_NAME
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not an object")
    for key, expected in (("id", str), ("name", str), ("accent", str)):
        if not isinstance(data.get(key), expected) or not data[key]:
            raise ValueError(f"{path} has no usable {key}")
    if data["id"] != Path(plugin_file).resolve().parent.name.replace("_", "-") \
            and data["id"].replace("-", "_") != Path(plugin_file).resolve().parent.name:
        raise ValueError(
            f"{path} says id {data['id']}, which is not its folder "
            f"{Path(plugin_file).resolve().parent.name}")
    return data


def plugin_defaults(plugin_file: str | Path) -> dict:
    """The `GamePlugin` fields that are the game's own metadata."""
    data = manifest(plugin_file)
    defaults = {
        "plugin_id": data["id"],
        "name": data["name"],
        "accent": data["accent"],
        "process_names": tuple(data.get("processNames", ())),
        "can_launch": data.get("canLaunch", True) is not False,
        "mods_load": data.get("modsLoad", False) is True,
    }
    return defaults


def install_spec(plugin_file: str | Path, **overrides) -> GameInstallSpec | None:
    """The installation descriptor from the manifest, or None when the game
    has no install to locate (Blank, which ships with the editor)."""
    data = manifest(plugin_file).get("installation")
    if not data:
        return None
    fields = {
        "root_env": data["rootEnv"],
        "required_paths": tuple(data["requiredPaths"]),
        "executable": data["executable"],
        "steam_app_id": data["steamAppId"],
        "install_dir_names": tuple(data["installDirNames"]),
        "default_roots": tuple(Path(root) for root in data["defaultRoots"]),
    }
    optional = {
        "data_env": data.get("dataEnv"),
        "art_app_id": data.get("artAppId"),
        "launch_path": data.get("launchPath", ""),
        "reshade_root": data.get("reshadeRoot", ""),
        "reshade_renderer": data.get("reshadeRenderer", ""),
        "prepare_on_scan": data.get("prepareOnScan", False) is True,
    }
    fields.update(optional)
    fields.update(overrides)
    return GameInstallSpec(**fields)


def project_spec(plugin_file: str | Path, default_root: Path, *,
                 template_root: Path | None = None, **overrides) -> ModProjectSpec | None:
    """The editable-project descriptor, with the folder this machine uses.

    `default_root` is passed in because it is the reader's own folder - under
    their Documents, or wherever they moved it - not a property of the game.
    """
    data = manifest(plugin_file).get("projects")
    if not data:
        return None
    plugin_directory = Path(plugin_file).resolve().parent
    fields = {
        "root_env": data["rootEnv"],
        "default_root": Path(default_root),
        "required_paths": tuple(data["requiredPaths"]),
    }
    if data.get("requiredAny"):
        fields["required_any"] = tuple(tuple(group) for group in data["requiredAny"])
    if data.get("contentTypes"):
        fields["content_types"] = tuple(tuple(entry) for entry in data["contentTypes"])
    template = template_root
    if template is None and data.get("templateRoot"):
        template = plugin_directory / data["templateRoot"]
    if template:
        fields["template_root"] = Path(template)
    fields.update(overrides)
    return ModProjectSpec(**fields)


def loading_quotes(plugin_id: str) -> list[str]:
    """The lines this game shows while it opens, in order, without repeats."""
    for path in sorted((Path(__file__).resolve().parents[1] / "plugins").iterdir()):
        if not (path / MANIFEST_NAME).is_file():
            continue
        data = manifest(path / "plugin.py") if (path / "plugin.py").is_file() else None
        if data and data["id"] == plugin_id:
            return list(dict.fromkeys(data.get("loadingQuotes", [])))
    return []
