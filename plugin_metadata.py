"""Required documentation metadata for every discovered Lexeditor game plugin.

This contract is intentionally runtime-visible: a newly discovered plugin is not
considered valid until its Credits and Mod Loading documentation exist. CI uses
the same functions, so the authoring checklist and the executable enforce the
same rules.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PLUGIN_ID_PATTERN = re.compile(r"\bplugin_id\s*=\s*['\"]([^'\"]+)['\"]")
CREDIT_GROUPS = ("contributions", "thanks", "licenses")
MOD_LOADING_FIELDS = ("loader", "structure", "overriding")
PLACEHOLDER_MARKERS = ("todo", "tbd", "template only", "fill this in", "replace me")


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as error:
        raise ValueError(f"Required plugin metadata file is missing: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read plugin metadata file {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Plugin metadata must be a JSON object: {path}")
    return value


def static_plugin_ids(root: Path = ROOT) -> set[str]:
    """Read declared plugin IDs without importing game code."""
    ids: set[str] = set()
    for plugin_path in sorted((Path(root) / "games").glob("*/plugin.py")):
        source = plugin_path.read_text(encoding="utf-8")
        matches = set(PLUGIN_ID_PATTERN.findall(source))
        if len(matches) != 1:
            relative = plugin_path.relative_to(root)
            raise ValueError(
                f"{relative} must use one consistent literal plugin_id; found "
                + (", ".join(sorted(matches)) if matches else "none")
            )
        plugin_id = next(iter(matches))
        if plugin_id in ids:
            raise ValueError(f"Duplicate plugin id in source tree: {plugin_id}")
        ids.add(plugin_id)
    if not ids:
        raise ValueError("Lexeditor found no plugin.py files to document")
    return ids


def _exact_plugin_set(document: dict, plugin_ids: set[str], label: str) -> dict:
    plugins = document.get("plugins")
    if not isinstance(plugins, dict):
        raise ValueError(f"{label} must contain a plugins object")
    present = set(plugins)
    missing = sorted(plugin_ids - present)
    unexpected = sorted(present - plugin_ids)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unexpected:
            details.append("unexpected " + ", ".join(unexpected))
        raise ValueError(f"{label} plugin IDs do not match discovered plugins: {'; '.join(details)}")
    return plugins


def validate_credits_bundle(document: dict, plugin_ids: Iterable[str]) -> None:
    """Require an explicit, non-empty Credits statement for every plugin."""
    ids = set(plugin_ids)
    plugins = _exact_plugin_set(document, ids, "Credits")
    for plugin_id in sorted(ids):
        section = plugins[plugin_id]
        if not isinstance(section, dict):
            raise ValueError(f"{plugin_id} Credits entry must be an object")
        count = 0
        for group in CREDIT_GROUPS:
            rows = section.get(group, [])
            if not isinstance(rows, list):
                raise ValueError(f"{plugin_id} Credits {group} must be a list")
            count += len(rows)
            for index, row in enumerate(rows):
                if not isinstance(row, dict) or not str(row.get("name", "")).strip():
                    raise ValueError(f"{plugin_id} Credits {group}[{index}] needs a name")
                if group != "licenses" and not str(row.get("role", "")).strip():
                    raise ValueError(f"{plugin_id} Credits {group}[{index}] needs a role")
                url = str(row.get("url", "")).strip()
                if url and not url.startswith(("https://", "http://")):
                    raise ValueError(f"{plugin_id} Credits {group}[{index}] has an invalid web URL")
        if count == 0:
            raise ValueError(
                f'{plugin_id} has an empty Credits section. Credit every project, document, tool, '
                'or person that materially informed the plugin. If there truly was nobody else, '
                'add an explicit contribution such as "Nobody but myself" instead of leaving it blank.'
            )


def validate_mod_loading(document: dict, plugin_ids: Iterable[str]) -> None:
    """Require the standardized loader/structure/override explanation."""
    ids = set(plugin_ids)
    plugins = _exact_plugin_set(document, ids, "Mod Loading")
    required = set(MOD_LOADING_FIELDS)
    for plugin_id in sorted(ids):
        section = plugins[plugin_id]
        if not isinstance(section, dict) or set(section) != required:
            raise ValueError(
                f"{plugin_id} Mod Loading entry must contain exactly: "
                + ", ".join(MOD_LOADING_FIELDS)
            )
        for field in MOD_LOADING_FIELDS:
            text = section[field]
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"{plugin_id} Mod Loading {field} is empty")
            lowered = text.casefold()
            if plugin_id != "blank" and any(marker in lowered for marker in PLACEHOLDER_MARKERS):
                raise ValueError(f"{plugin_id} Mod Loading {field} still contains template text")


def validate_repository_metadata(plugin_ids: Iterable[str] | None = None,
                                 root: Path = ROOT) -> None:
    """Validate the exact metadata bundle shipped with the application."""
    root = Path(root)
    ids = set(plugin_ids) if plugin_ids is not None else static_plugin_ids(root)
    validate_credits_bundle(_read_json(root / "ui" / "credits.json"), ids)
    validate_mod_loading(_read_json(root / "ui" / "mod-loading.json"), ids)


def main() -> int:
    validate_repository_metadata()
    print("plugin metadata contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
