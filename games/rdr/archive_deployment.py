"""Transactional RDR1 project-archive deployment through Ultimate ASI Loader's update folder."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from process_probe import live_processes


STATE_NAME = ".lexeditor-rdr-archives.json"
BACKUP_ROOT_NAME = ".lexeditor-rdr-archive-backups"
UPDATE_FOLDER = "update"


@dataclass(frozen=True)
class ArchiveSpec:
    name: str
    source_relative: Path
    override_root: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(document, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _state_path(game_root: Path) -> Path:
    return game_root / STATE_NAME


def _load_state(game_root: Path) -> dict:
    path = _state_path(game_root)
    if not path.is_file():
        return {"version": 1, "gameRoot": str(game_root), "entries": {}}
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(document, dict) or document.get("version") != 1 or
            document.get("gameRoot") != str(game_root) or
            not isinstance(document.get("entries"), dict)):
        raise ValueError("RDR archive deployment state is invalid or belongs to another game root")
    return document


def _override_files(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        lower = path.name.casefold()
        if lower.endswith(".lexeditor.bak") or ".lexeditor." in lower or lower.endswith(".tmp"):
            continue
        relative = path.relative_to(root).as_posix()
        if not relative or relative.startswith("../"):
            raise ValueError(f"Invalid RDR override path: {path}")
        result[f"root/{relative}"] = path.resolve()
    return result


def _override_hashes(files: dict[str, Path]) -> dict[str, str]:
    return {name: sha256_file(path) for name, path in sorted(files.items())}


def _write_manifest(path: Path, files: dict[str, Path]) -> None:
    lines = [f"{archive_path}\t{source}" for archive_path, source in sorted(files.items())]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_builder(tool: Path, source: Path, output: Path, manifest: Path) -> None:
    result = subprocess.run(
        [str(tool), "build-copy", str(source), str(output), str(manifest)],
        cwd=str(tool.parent), capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"RPF6 copy build failed for {source.name}: {detail}")


def _validate_owned_state(game_root: Path, state: dict) -> None:
    for relative, entry in state.get("entries", {}).items():
        target = game_root / Path(relative)
        expected = entry.get("afterSha256")
        if not target.is_file() or not expected or sha256_file(target) != expected:
            raise RuntimeError(
                f"Deployed RDR archive changed outside Lexeditor; refusing to overwrite it: {target}")
        original_hash = entry.get("originalSha256")
        backup_text = entry.get("originalBackup")
        if original_hash:
            if not backup_text:
                raise RuntimeError(f"Deployment state lost its original backup path: {target}")
            backup = game_root / Path(backup_text)
            if not backup.is_file() or sha256_file(backup) != original_hash:
                raise RuntimeError(f"Original update archive backup is missing or changed: {backup}")


def deployment_status(game_root: Path, specs: tuple[ArchiveSpec, ...]) -> dict:
    game_root = game_root.resolve()
    try:
        state = _load_state(game_root)
        state_error = ""
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        state = {"version": 1, "gameRoot": str(game_root), "entries": {}}
        state_error = str(error)
    rows = []
    for spec in specs:
        source = (game_root / spec.source_relative).resolve()
        target_relative = Path(UPDATE_FOLDER) / spec.source_relative
        target = (game_root / target_relative).resolve()
        overrides = _override_files(spec.override_root)
        entry = state.get("entries", {}).get(target_relative.as_posix(), {})
        deployed_hash = entry.get("afterSha256")
        current_hash = sha256_file(target) if target.is_file() else None
        current_overrides = _override_hashes(overrides)
        rows.append({
            "name": spec.name,
            "source": str(source),
            "target": str(target),
            "overrideCount": len(overrides),
            "overrideHashes": current_overrides,
            "deployed": bool(deployed_hash and current_hash == deployed_hash and
                             entry.get("overrideHashes") == current_overrides),
            "changedSinceDeploy": bool(deployed_hash and current_hash != deployed_hash),
            "sourceExists": source.is_file(),
            "targetExists": target.is_file(),
        })
    return {
        "stateFile": str(_state_path(game_root)),
        "stateError": state_error,
        "updateRoot": str(game_root / UPDATE_FOLDER),
        "rows": rows,
        "pending": any(row["overrideCount"] and not row["deployed"] for row in rows),
        "active": bool(state.get("entries")),
    }


def deploy_archives(game_root: Path, tool: Path, specs: tuple[ArchiveSpec, ...],
                    *, builder=_run_builder, running_check=live_processes) -> dict:
    game_root = game_root.resolve()
    tool = tool.resolve()
    if running_check(("RDR.exe",)):
        raise RuntimeError("Close RDR1 before deploying project archives")
    if not tool.is_file():
        raise FileNotFoundError(f"RPF6 bridge is missing: {tool}")
    if not (game_root / "winmm.dll").is_file():
        raise FileNotFoundError("Ultimate ASI Loader/RedHook winmm.dll is required for update-folder deployment")

    state = _load_state(game_root)
    _validate_owned_state(game_root, state)
    old_entries = state.get("entries", {})
    requested: dict[str, dict] = {}
    build_root = game_root / UPDATE_FOLDER / f".lexeditor-build-{uuid.uuid4().hex}"
    build_root.mkdir(parents=True, exist_ok=False)
    try:
        for spec in specs:
            overrides = _override_files(spec.override_root)
            if not overrides:
                continue
            source = (game_root / spec.source_relative).resolve()
            if not source.is_file():
                raise FileNotFoundError(f"Installed RDR archive is missing: {source}")
            with source.open("rb") as stream:
                if stream.read(4) != b"RPF6":
                    raise ValueError(f"Expected an RPF6 source archive: {source}")
            manifest = build_root / f"{spec.name}.tsv"
            output = build_root / spec.source_relative.name
            _write_manifest(manifest, overrides)
            builder(tool, source, output, manifest)
            if not output.is_file():
                raise RuntimeError(f"RPF6 builder reported success without output: {output}")
            if sha256_file(source) == sha256_file(output):
                raise RuntimeError(f"RPF6 output for {spec.name} is byte-identical despite project replacements")
            target_relative = (Path(UPDATE_FOLDER) / spec.source_relative).as_posix()
            requested[target_relative] = {
                "name": spec.name,
                "source": source,
                "sourceSha256": sha256_file(source),
                "staging": output,
                "overrideHashes": _override_hashes(overrides),
            }

        all_relatives = sorted(set(old_entries) | set(requested))
        if not all_relatives:
            return {**deployment_status(game_root, specs), "changed": 0, "message": "No project archive overrides exist"}

        transaction = game_root / BACKUP_ROOT_NAME / ("txn-" + uuid.uuid4().hex)
        transaction.mkdir(parents=True, exist_ok=False)
        actions = []
        new_entries: dict[str, dict] = {}
        try:
            for index, relative in enumerate(all_relatives):
                target = (game_root / Path(relative)).resolve()
                if game_root != target and game_root not in target.parents:
                    raise ValueError(f"Deployment target escapes game root: {target}")
                target.parent.mkdir(parents=True, exist_ok=True)
                old = old_entries.get(relative)
                request = requested.get(relative)
                rollback = transaction / f"{index:03}.current.rpf"
                had_target = target.is_file()
                if had_target:
                    os.replace(target, rollback)
                action = {"target": target, "rollback": rollback, "hadTarget": had_target,
                          "restoredBackup": None, "newTarget": False}
                actions.append(action)

                if request:
                    if old:
                        original_hash = old.get("originalSha256")
                        original_backup = old.get("originalBackup")
                    else:
                        original_hash = sha256_file(rollback) if had_target else None
                        original_backup = None
                        if had_target:
                            persistent_dir = game_root / BACKUP_ROOT_NAME / ("original-" + uuid.uuid4().hex)
                            persistent_dir.mkdir(parents=True, exist_ok=False)
                            backup = persistent_dir / target.name
                            os.replace(rollback, backup)
                            action["rollback"] = backup
                            action["originalCreated"] = True
                            original_backup = backup.relative_to(game_root).as_posix()
                    os.replace(request["staging"], target)
                    action["newTarget"] = True
                    after_hash = sha256_file(target)
                    new_entries[relative] = {
                        "name": request["name"],
                        "sourceSha256": request["sourceSha256"],
                        "afterSha256": after_hash,
                        "originalSha256": original_hash,
                        "originalBackup": original_backup,
                        "overrideHashes": request["overrideHashes"],
                    }
                else:
                    if old and old.get("originalSha256"):
                        backup = game_root / Path(old["originalBackup"])
                        os.replace(backup, target)
                        action["restoredBackup"] = backup

            new_state = {"version": 1, "gameRoot": str(game_root), "entries": new_entries}
            if new_entries:
                _atomic_json(_state_path(game_root), new_state)
            else:
                _state_path(game_root).unlink(missing_ok=True)

            for action in actions:
                rollback = action["rollback"]
                if action.get("originalCreated"):
                    continue
                if rollback.is_file():
                    rollback.unlink()
            shutil.rmtree(transaction, ignore_errors=True)
            return {**deployment_status(game_root, specs), "changed": len(all_relatives),
                    "message": "Project archive copies deployed through the update folder"}
        except Exception:
            for action in reversed(actions):
                target: Path = action["target"]
                rollback: Path = action["rollback"]
                restored_backup = action.get("restoredBackup")
                try:
                    if restored_backup and target.is_file():
                        os.replace(target, restored_backup)
                    elif target.is_file():
                        target.unlink()
                    if rollback.is_file():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(rollback, target)
                except OSError:
                    pass
            raise
    finally:
        shutil.rmtree(build_root, ignore_errors=True)


def revert_archives(game_root: Path, specs: tuple[ArchiveSpec, ...], *, running_check=live_processes) -> dict:
    game_root = game_root.resolve()
    if running_check(("RDR.exe",)):
        raise RuntimeError("Close RDR1 before reverting project archives")
    state = _load_state(game_root)
    _validate_owned_state(game_root, state)
    entries = state.get("entries", {})
    if not entries:
        return {**deployment_status(game_root, specs), "changed": 0, "message": "No Lexeditor archive deployment is active"}

    transaction = game_root / BACKUP_ROOT_NAME / ("revert-" + uuid.uuid4().hex)
    transaction.mkdir(parents=True, exist_ok=False)
    actions = []
    try:
        for index, (relative, entry) in enumerate(sorted(entries.items())):
            target = game_root / Path(relative)
            rollback = transaction / f"{index:03}.current.rpf"
            os.replace(target, rollback)
            action = {"target": target, "rollback": rollback, "backup": None}
            actions.append(action)
            if entry.get("originalSha256"):
                backup = game_root / Path(entry["originalBackup"])
                os.replace(backup, target)
                action["backup"] = backup
                if sha256_file(target) != entry["originalSha256"]:
                    raise RuntimeError(f"Restored archive did not match its original hash: {target}")
        _state_path(game_root).unlink(missing_ok=True)
        for action in actions:
            action["rollback"].unlink(missing_ok=True)
            backup = action.get("backup")
            if backup:
                try:
                    backup.parent.rmdir()
                except OSError:
                    pass
        shutil.rmtree(transaction, ignore_errors=True)
        return {**deployment_status(game_root, specs), "changed": len(entries),
                "message": "Lexeditor archive copies reverted; installed RPF archives were never modified"}
    except Exception:
        for action in reversed(actions):
            target = action["target"]
            backup = action.get("backup")
            rollback = action["rollback"]
            try:
                if backup and target.is_file():
                    os.replace(target, backup)
                elif target.is_file():
                    target.unlink()
                if rollback.is_file():
                    os.replace(rollback, target)
            except OSError:
                pass
        raise
