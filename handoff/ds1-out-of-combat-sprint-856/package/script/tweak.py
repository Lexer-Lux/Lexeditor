"""Emit one native patch description through Lexeditor's trusted script API."""
from __future__ import annotations

import json
from .native_patch import specification


def build(settings: dict, context) -> dict[str, str]:
    """The shared loader handles trust, executable identity, Apply and Restore."""
    if not isinstance(settings, dict) or settings:
        raise ValueError("This mod has no settings beyond its library enable switch")
    return {"native/out-of-combat-sprint.json": json.dumps(specification(), indent=2) + "\n"}
