"""Installed Project Zomboid Build 42 acceptance preflight.

This module is intentionally passive: it validates a real game root and an
owned Lexeditor deployment, then verifies that the deployed script tree is
still structurally readable. It never launches the game or claims that a mod
loaded successfully in-game.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re

from . import core, zedscript


_MODS_BLOCK_RE = re.compile(r"(?is)(?:^|\n)\s*mods\s*\{(?P<body>.*?)\}")
_MOD_ENTRY_RE = re.compile(
    r"(?im)^\s*mod\s*=\s*(?P<id>.*?)\s*,\s*(?://.*)?$"
)


def _check(checks: list[dict], check_id: str, ok: bool, detail: str) -> bool:
    checks.append({"id": check_id, "ok": bool(ok), "detail": detail})
    return bool(ok)


def _mod_list_evidence(path: Path, mod_id: str, user_root: Path) -> dict:
    """Read one PZ mods/default.txt or save mods.txt without changing it."""
    relative = str(path)
    try:
        relative = path.relative_to(user_root).as_posix()
    except ValueError:
        pass
    if not path.is_file():
        return {
            "path": relative,
            "exists": False,
            "enabled": False,
            "modIds": [],
            "error": "",
        }
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        return {
            "path": relative,
            "exists": True,
            "enabled": False,
            "modIds": [],
            "error": str(error),
        }
    match = _MODS_BLOCK_RE.search(text)
    if match is None:
        return {
            "path": relative,
            "exists": True,
            "enabled": False,
            "modIds": [],
            "error": "No mods { ... } block found",
        }
    mod_ids = [
        entry.group("id").strip()
        for entry in _MOD_ENTRY_RE.finditer(match.group("body"))
        if entry.group("id").strip()
    ]
    enabled = bool(mod_id) and any(value == mod_id for value in mod_ids)
    return {
        "path": relative,
        "exists": True,
        "enabled": enabled,
        "modIds": mod_ids,
        "error": "",
    }


def _activation_evidence(user_root: Path, mod_id: str) -> dict:
    """Report existing default/save activation evidence without requiring it."""
    default_list = _mod_list_evidence(
        user_root / "mods" / "default.txt", mod_id, user_root
    )
    save_root = user_root / "Saves"
    save_lists: list[dict] = []
    if save_root.is_dir():
        for path in sorted(save_root.rglob("mods.txt")):
            save_lists.append(_mod_list_evidence(path, mod_id, user_root))
    matching_saves = [row for row in save_lists if row["enabled"]]
    parse_errors = [row for row in save_lists if row["error"]]
    if default_list["error"]:
        parse_errors.insert(0, default_list)
    return {
        "defaultList": default_list,
        "saveListsScanned": len(save_lists),
        "matchingSaves": matching_saves,
        "parseErrors": parse_errors,
        "enabledAnywhere": bool(default_list["enabled"] or matching_saves),
        "boundary": (
            "Activation files are evidence only. Their presence does not prove the "
            "game successfully discovered, loaded, or executed the deployed mod."
        ),
    }


def inspect(game_root: Path, project_root: Path, user_root: Path) -> dict:
    """Return a truthful preflight report for one installed-game acceptance run."""
    game_root = Path(game_root).expanduser().resolve()
    project_root = Path(project_root).expanduser().resolve()
    user_root = Path(user_root).expanduser().resolve()
    checks: list[dict] = []

    _check(checks, "game-root", game_root.is_dir(), str(game_root))
    _check(
        checks,
        "game-executable",
        (game_root / "ProjectZomboid64.exe").is_file(),
        str(game_root / "ProjectZomboid64.exe"),
    )
    _check(
        checks,
        "game-scripts",
        (game_root / "media" / "scripts").is_dir(),
        str(game_root / "media" / "scripts"),
    )
    _check(
        checks,
        "build42-generated-scripts",
        (game_root / "media" / "scripts" / "generated").is_dir(),
        str(game_root / "media" / "scripts" / "generated"),
    )

    source_id = ""
    source_name = ""
    source_info_path = ""
    try:
        source = core.read_mod_info(project_root)
        source_fields = source.get("fields", {})
        source_id = str(source_fields.get("id", "")).strip()
        source_name = str(source_fields.get("name", "")).strip()
        source_info_path = str(source.get("path", ""))
        source_ok = bool(source_id and source_name)
        source_detail = (
            f"{source_info_path} name={source_name} id={source_id}"
            if source_ok else f"{source_info_path} is missing required name/id"
        )
    except (core.ProjectZomboidError, OSError) as error:
        source_ok = False
        source_detail = str(error)
    _check(checks, "source-mod-info", source_ok, source_detail)

    state = {}
    state_error = ""
    try:
        state = core.deployment_state(project_root)
    except (core.ProjectZomboidError, OSError) as error:
        state_error = str(error)
    target_value = state.get("target") if isinstance(state, dict) else ""
    raw_target = Path(target_value).expanduser() if isinstance(target_value, str) and target_value else None
    target = raw_target.resolve() if raw_target else None
    target_is_link = bool(raw_target and raw_target.is_symlink())
    owned = bool(state.get("owned")) if isinstance(state, dict) else False
    _check(
        checks,
        "owned-deployment",
        owned and not target_is_link,
        state_error or (
            f"{target} ({state.get('fileCount', 0)} files)"
            if target else "No Lexeditor deployment record"
        ),
    )

    expected_target = (user_root / "mods" / project_root.name).resolve()
    target_ok = bool(target and target == expected_target and not target_is_link)
    _check(
        checks,
        "deployment-target",
        target_ok,
        f"expected {expected_target}; actual {target if target else '<none>'}",
    )

    deployed_id = ""
    deployed_name = ""
    deployed_detail = "Deployment target is unavailable"
    if target and target.is_dir() and not target_is_link:
        try:
            deployed = core.read_mod_info(target)
            deployed_fields = deployed.get("fields", {})
            deployed_id = str(deployed_fields.get("id", "")).strip()
            deployed_name = str(deployed_fields.get("name", "")).strip()
            deployed_detail = (
                f"{deployed.get('path', '')} name={deployed_name} id={deployed_id}"
            )
        except (core.ProjectZomboidError, OSError) as error:
            deployed_detail = str(error)
    _check(
        checks,
        "deployed-mod-info",
        bool(deployed_id and deployed_name),
        deployed_detail,
    )
    _check(
        checks,
        "mod-identity-match",
        bool(
            source_id and source_name
            and source_id == deployed_id
            and source_name == deployed_name
        ),
        (
            f"source={source_name or '<missing>'}/{source_id or '<missing>'}; "
            f"deployed={deployed_name or '<missing>'}/{deployed_id or '<missing>'}"
        ),
    )

    inventory = {"rows": [], "counts": {}, "errors": []}
    inventory_detail = "Deployment target is unavailable"
    if target and target.is_dir() and not target_is_link:
        try:
            inventory = zedscript.inventory(target)
            errors = inventory.get("errors", [])
            inventory_detail = (
                f"{len(inventory.get('rows', []))} recognized top-level records; "
                f"{len(errors)} parse error(s)"
            )
        except (core.ProjectZomboidError, OSError) as error:
            inventory = {"rows": [], "counts": {}, "errors": [{"error": str(error)}]}
            inventory_detail = str(error)
    _check(
        checks,
        "deployed-script-parse",
        not inventory.get("errors"),
        inventory_detail,
    )

    activation = _activation_evidence(user_root, source_id)
    ready = all(check["ok"] for check in checks)
    return {
        "preflightReady": ready,
        "gameRoot": str(game_root),
        "projectRoot": str(project_root),
        "userRoot": str(user_root),
        "modName": source_name,
        "modId": source_id,
        "deploymentTarget": str(target) if target else "",
        "checks": checks,
        "scriptInventory": {
            "recordCount": len(inventory.get("rows", [])),
            "counts": inventory.get("counts", {}),
            "errors": inventory.get("errors", []),
        },
        "activationEvidence": activation,
        "manualGameTest": [
            "Launch the validated current Project Zomboid Build 42 stable installation.",
            f"Open Mods and confirm {source_name or source_id or '<mod>'} appears; enable it.",
            "Start or load a disposable test world with the mod enabled.",
            "Exercise representative edited content from the deployed project.",
            "Treat any missing mod, script load error, or incorrect edited behavior as a failed installed-game acceptance.",
        ],
        "acceptanceBoundary": (
            "Preflight only. A successful report proves the install/deployment shape "
            "and deployed-script readability, not that Project Zomboid loaded the mod "
            "or representative edited scripts successfully in-game."
        ),
    }


def _required_path(
    value: str | None, label: str, parser: argparse.ArgumentParser
) -> Path:
    if not value:
        parser.error(f"{label} is required (argument or environment variable)")
    return Path(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a real Project Zomboid install and Lexeditor-owned local-mod "
            "deployment before manual in-game acceptance."
        )
    )
    parser.add_argument(
        "--game-root",
        default=os.environ.get("LEXEDITOR_PROJECT_ZOMBOID_ROOT"),
        help=(
            "Project Zomboid install root "
            "(defaults to LEXEDITOR_PROJECT_ZOMBOID_ROOT)"
        ),
    )
    parser.add_argument(
        "--project-root",
        default=os.environ.get("LEXEDITOR_PROJECT_ZOMBOID_PROJECT"),
        help=(
            "Lexeditor mod project root "
            "(defaults to LEXEDITOR_PROJECT_ZOMBOID_PROJECT)"
        ),
    )
    parser.add_argument(
        "--user-root",
        default=os.environ.get(
            "LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT",
            str(Path.home() / "Zomboid"),
        ),
        help=(
            "Project Zomboid user-data root "
            "(defaults to LEXEDITOR_PROJECT_ZOMBOID_USER_ROOT or ~/Zomboid)"
        ),
    )
    args = parser.parse_args(argv)
    report = inspect(
        _required_path(args.game_root, "--game-root", parser),
        _required_path(args.project_root, "--project-root", parser),
        Path(args.user_root),
    )
    print(json.dumps(report, indent=2))
    return 0 if report["preflightReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
