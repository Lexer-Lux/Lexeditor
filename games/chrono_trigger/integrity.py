"""Cross-resource integrity audit for Chrono Trigger Steam projects."""

from __future__ import annotations

from pathlib import PurePosixPath

from .data import OverlayStore, load_scenes, normalize_virtual_path
from .worlds import load_worlds
from .world_scripts import load_world_script


def _issue(level: str, code: str, message: str, **context) -> dict:
    return {"level": level, "code": code, "message": message, **context}


def audit_project(store: OverlayStore, source: str = "mine") -> dict:
    """Check references we can prove from the currently integrated Steam layouts.

    The audit is deliberately conservative.  It reports missing referenced
    resources and malformed structured data, but does not reject loose files
    simply because they are new: CTExt is capable of adding archive-relative
    resources as well as replacing existing ones.
    """
    issues: list[dict] = []
    archive_paths = {entry.path.casefold() for entry in store.archive.entries}

    overlay_files = []
    if store.project_root.is_dir() and store.writable:
        root = store.project_root.resolve()
        for target in sorted(store.project_root.rglob("*")):
            if target.is_symlink():
                issues.append(_issue(
                    "error", "project-symlink",
                    "Project contains a symlink; deployment refuses symlinked files.",
                    path=str(target),
                ))
                continue
            if not target.is_file():
                continue
            relative = target.resolve().relative_to(root).as_posix()
            if relative in {"lexeditor-project.json", ".lexeditor-deployment.json"}:
                continue
            try:
                virtual = normalize_virtual_path(relative)
            except ValueError as error:
                issues.append(_issue("error", "unsafe-project-path", str(error), path=relative))
                continue
            overlay_files.append(virtual)
            if virtual.casefold() not in archive_paths:
                issues.append(_issue(
                    "info", "new-loose-resource",
                    "Project contains a loose resource that is not present in the Vanilla ARC1 index.",
                    path=virtual,
                ))

    scene_count = 0
    try:
        scenes = load_scenes(store, source, limit=250)
        scene_count = scenes["matchCount"]
        for row in scenes["rows"]:
            script_id = int(row["values"]["scriptIndex"])
            event_path = f"Game/field/atel/Atel_{script_id:04d}.dat"
            if not store.exists(event_path, source):
                issues.append(_issue(
                    "warning", "missing-field-script",
                    f"Scene {row['id']} references missing field event {script_id}.",
                    sceneId=row["id"], scriptId=script_id, path=event_path,
                ))
    except Exception as error:
        issues.append(_issue(
            "error", "scene-audit-failed",
            f"Scene headers could not be audited: {error}",
        ))

    world_count = 0
    try:
        worlds = load_worlds(store, source)
        world_count = len(worlds["rows"])
        for row in worlds["rows"]:
            world_id = int(row["id"])
            exit_id = int(row["values"]["exits"])
            script_id = int(row["values"]["script"])
            exit_path = f"Game/world/EventTable/EventTable_{exit_id:04d}.dat"
            script_path = f"Game/world/esl/Event_{script_id:04d}.dat"
            if not store.exists(exit_path, source):
                issues.append(_issue(
                    "warning", "missing-world-event-table",
                    f"World {world_id} references missing EventTable {exit_id}.",
                    worldId=world_id, tableId=exit_id, path=exit_path,
                ))
            if not store.exists(script_path, source):
                issues.append(_issue(
                    "warning", "missing-world-script",
                    f"World {world_id} references missing world script {script_id}.",
                    worldId=world_id, scriptId=script_id, path=script_path,
                ))
                continue
            try:
                script = load_world_script(store, world_id, source)
            except Exception as error:
                issues.append(_issue(
                    "error", "world-script-audit-failed",
                    f"World {world_id} script could not be decoded: {error}",
                    worldId=world_id, path=script_path,
                ))
                continue
            if not script["complete"]:
                problem = script.get("problem") or {}
                issues.append(_issue(
                    "info", "partial-world-script-disassembly",
                    f"World {world_id} script disassembly stops at byte {problem.get('offset', script['decodedBytes'])}; remaining commands are not guessed.",
                    worldId=world_id, path=script_path,
                    problem=problem,
                ))
    except Exception as error:
        issues.append(_issue(
            "error", "world-audit-failed",
            f"Overworld headers could not be audited: {error}",
        ))

    counts = {level: sum(issue["level"] == level for issue in issues)
              for level in ("error", "warning", "info")}
    return {
        "kind": "chrono-trigger-project-audit",
        "source": source,
        "projectRoot": str(store.project_root),
        "overlayFiles": len(overlay_files),
        "sceneHeaders": scene_count,
        "worldHeaders": world_count,
        "counts": counts,
        "ok": counts["error"] == 0,
        "issues": issues,
    }
