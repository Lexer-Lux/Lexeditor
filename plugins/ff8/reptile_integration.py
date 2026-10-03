"""Wire issue #323's mod-owned Reptile metadata into existing FF8 editor APIs.

This deliberately wraps the stable generic Enemy/settings surfaces instead of
reserving an unused c0m*.dat bit. The runtime consumes the same project-owned
configuration separately.
"""
from __future__ import annotations
from core.numeric_values import integer_value

from . import formats, gameplay_settings, paths, reptile_atb


FIELD_NAME = "reptile"
_FIELD = {
    "field": FIELD_NAME,
    "label": "Reptile",
    "group": "Properties",
    "help": (
        "Lexeditor-only classification used by the optional Reptile tweak. "
        "Ice moves multiply this enemy's ATB speed by 0.92 and Fire moves by 1.08."
    ),
    "minimum": 0,
    "maximum": 1,
    "control": "boolean",
}
_installed = False


def _root_for_dataset(dataset: str):
    if dataset == "current":
        return paths.PROJECT_ROOT
    if dataset.startswith("mod:"):
        return formats._managed_root(dataset)
    return None


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    original_enemy_rows = formats.enemy_rows
    original_save_enemies = formats.save_enemies
    original_load_settings = gameplay_settings.load
    original_initialize_project = gameplay_settings.initialize_project

    def enemy_rows(dataset: str = "current") -> dict:
        payload = original_enemy_rows(dataset)
        root = _root_for_dataset(dataset)
        reptiles = set(reptile_atb.load(root)["enemyIds"]) if root is not None else set()
        for row in payload.get("rows", []):
            if not row.get("available"):
                continue
            row.setdefault("fields", []).append({
                **_FIELD,
                "value": int(row.get("id", -1)) in reptiles,
            })
        return payload

    def save_enemies(edits: list[dict]) -> dict:
        if not isinstance(edits, list):
            raise ValueError("Enemy edits must be an array")
        reptile_edits = []
        binary_edits = []
        seen = set()
        valid_ids = {int(row["com_id"]) for row in formats.MONSTERS}
        for edit in edits:
            if not isinstance(edit, dict) or set(edit) != {"id", "field", "value"}:
                raise ValueError("Enemy edit requires id, field and value")
            if not isinstance(edit["field"], str):
                raise ValueError("Enemy field must be text")
            if edit["field"] != FIELD_NAME:
                binary_edits.append(edit)
                continue
            monster_id = integer_value(edit["id"], "Reptile enemy id")
            if monster_id not in valid_ids or monster_id in seen:
                raise ValueError(f"Invalid or duplicate Reptile enemy edit: {monster_id}")
            seen.add(monster_id)
            if not isinstance(edit.get("value"), bool):
                raise ValueError("Reptile must be true or false")
            reptile_edits.append((monster_id, bool(edit["value"])))

        if reptile_edits:
            current = reptile_atb.load(paths.PROJECT_ROOT)
            ids = set(current["enemyIds"])
            for monster_id, enabled in reptile_edits:
                if enabled:
                    ids.add(monster_id)
                else:
                    ids.discard(monster_id)
            enabled = bool(current["enabled"] or ids)
            reptile_atb.build(enabled=enabled, reptile_enemy_ids=ids)
        result = original_save_enemies(binary_edits) if binary_edits else {
            "saved": 0, "file": "", "files": []
        }
        if reptile_edits:
            target = reptile_atb.write(
                paths.PROJECT_ROOT,
                enabled=enabled,
                reptile_enemy_ids=ids,
            )
            result = dict(result)
            result["saved"] = int(result.get("saved", 0)) + len(reptile_edits)
            files = list(result.get("files", []))
            if str(target) not in files:
                files.append(str(target))
            result["files"] = files
            if not result.get("file"):
                result["file"] = str(target)
        return result

    def load_settings(project_root=None, game_root=None, runtime_root=None) -> dict:
        result = original_load_settings(project_root, game_root, runtime_root)
        project = (project_root or paths.PROJECT_ROOT).resolve()
        config = reptile_atb.load(project)
        result["reptileAtb"] = bool(config["enabled"])
        result["reptileAtbAvailable"] = True
        result["reptileEnemyCount"] = len(config["enemyIds"])
        result["reptileIceMultiplier"] = reptile_atb.ICE_MULTIPLIER
        result["reptileFireMultiplier"] = reptile_atb.FIRE_MULTIPLIER
        return result

    def initialize_project(project_root) -> None:
        original_initialize_project(project_root)
        reptile_atb.write(project_root, enabled=False, reptile_enemy_ids=[])

    formats.enemy_rows = enemy_rows
    formats.save_enemies = save_enemies
    gameplay_settings.load = load_settings
    gameplay_settings.initialize_project = initialize_project
