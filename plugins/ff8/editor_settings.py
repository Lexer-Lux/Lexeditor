"""Editor furniture settings for the Final Fantasy VIII plugin.

Gameplay tweaks live per mod; these are Lexeditor's own FF8 preferences, so
they live beside the local data rather than in the project. Every setting is
off unless Lexer turns it on.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from . import paths


ENV_VAR = "LEXEDITOR_FF8_EDITOR_SETTINGS"
DEFAULTS = {"showNewGame": False, "delingFieldLayout": False}


def settings_path() -> Path:
    """Where this machine's FF8 editor settings live."""
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override)
    return paths.LOCAL_DATA_ROOT / "ff8-editor.json"


def load() -> dict:
    """Read the settings, defaulting anything missing or unreadable to off."""
    try:
        payload = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return dict(DEFAULTS)
    if not isinstance(payload, dict):
        return dict(DEFAULTS)
    return {key: payload.get(key, default) if isinstance(payload.get(key, default), bool)
            else default for key, default in DEFAULTS.items()}


def save(patch: dict) -> dict:
    """Persist known boolean settings; unknown keys and types are rejected."""
    if not isinstance(patch, dict):
        raise ValueError("The FF8 editor settings update must be an object")
    unknown = sorted(set(patch) - set(DEFAULTS))
    if unknown:
        raise ValueError(f"Unknown FF8 editor setting: {', '.join(unknown)}")
    for key, value in patch.items():
        if not isinstance(value, bool):
            raise ValueError(f"FF8 editor setting {key} must be true or false")
    merged = load()
    merged.update(patch)
    target = settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        prefix=".ff8-editor-", suffix=".json", dir=target.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump(merged, output, indent=2, sort_keys=True)
            output.write("\n")
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return merged
