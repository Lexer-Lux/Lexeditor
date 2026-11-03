"""Pinned, separate installation of Lexer's redistributable Verdite2 launcher."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile

from core.mod_library import digest, file_tree, package_root
from core.plugin_files import atomic_write, fetch_file, is_link
from core.plugin_manifest import install_spec
from core.native_port_settings import read_json

PIN = json.loads(Path(__file__).with_name("fork.json").read_text(encoding="utf-8"))
RECEIPT = ".lexeditor-port-files.json"
BACKUP = ".lexeditor-port-backup.json"
CRITICAL = ("Verdite2.exe", "bin/Verdite2.dll", *install_spec(__file__).required_paths,
            "content/src/patches/SeparateRun.cs",
            "content/src/patches/ViewDistanceFade.cs", "content/src/patches/ControlProfiles.cs",
            "content/src/patches/Analog.cs", "content/src/patches/EnemyTurn.cs",
            "content/src/patches/NativeNotifications.cs", "content/src/patches/RenderDistance.cs",
            "content/src/patches/TileWalk.cs", "content/src/patches/ModelWalk.cs",
            "content/config/onboarding.json", "content/manifest.txt")


def _write(path: Path, value: dict) -> None:
    atomic_write(path, (json.dumps(value, indent=2) + "\n").encode("utf-8"))


def _tree(root: Path) -> dict[str, str]:
    return {path.as_posix(): digest(root / path) for path in file_tree(root)}


def _safe_root(root: Path) -> Path:
    root = Path(root).absolute()
    if root == root.parent or any(is_link(path) for path in (root, *root.parents)):
        raise ValueError("Choose a separate real folder for Lexer's Verdite2 fork")
    return root.resolve()


def _paths(root: Path) -> tuple[Path, Path]:
    return root.parent / f".{root.name}.lexeditor-port-install.json", root.parent / f".{root.name}.lexeditor-port-stage"


def _verify_owned(root: Path) -> dict:
    marker = read_json(root / "lexeditor-port.json")
    receipt = read_json(root / RECEIPT)
    if marker.get("repository") != PIN["repository"] or receipt.get("repository") != PIN["repository"]:
        raise ValueError("This folder is not a managed Lexer Verdite2 fork; choose a separate folder")
    hashes = receipt.get("files")
    if not isinstance(hashes, dict) or not all(name in hashes for name in CRITICAL):
        raise ValueError("The fork installation receipt is incomplete")
    # file_tree refuses links, reparse points, unsafe paths and excessive trees.
    files = {path.as_posix() for path in file_tree(root)}
    if any(name not in files or digest(root / name) != expected for name, expected in hashes.items()):
        raise ValueError("Fork files changed outside Lexeditor; preserve those changes before updating")
    return hashes


def status(root: Path | None) -> dict:
    result = {"installed": False, "runtime": "Lexer's Verdite2 fork", "pinned": PIN["tag"],
              "version": "", "message": "Install the pinned Lexer Verdite2 fork before opening this editor."}
    if root is None:
        return result
    try:
        root = _safe_root(root)
        if _paths(root)[0].exists():
            result["message"] = "Repair the interrupted fork installation before opening the editor."
            return result
        marker = read_json(root / "lexeditor-port.json")
        receipt = read_json(root / RECEIPT)
        result["version"] = marker.get("version", "")
        exact = all(marker.get(key) == PIN[key] for key in ("repository", "sourceRevision", "serial", "version", "tag"))
        hashes = receipt.get("files", {})
        intact = receipt.get("repository") == PIN["repository"] and all(
            name in hashes and (root / name).is_file()
            and not any(is_link(path) for path in (root / name, *(root / name).parents) if path == root or root in path.parents)
            and digest(root / name) == hashes[name] for name in CRITICAL)
        result["installed"] = bool(exact and intact)
        if result["installed"]:
            result["message"] = ""
    except (OSError, ValueError, TypeError) as error:
        result["message"] = str(error)
    return result


def _discard_backup(path: Path) -> None:
    if not path.exists():
        return
    if is_link(path):
        raise ValueError("The fork backup is linked; it was preserved")
    record = read_json(path / BACKUP)
    actual = _tree(path)
    actual.pop(BACKUP, None)
    if record.get("repository") != PIN["repository"] or actual != record.get("files"):
        raise ValueError("The previous fork backup was edited; it was preserved")
    shutil.rmtree(path)


def _verify_stage(stage: Path) -> None:
    """An incomplete copy can be retried, but never erase edits to that copy."""
    receipt = read_json(stage / RECEIPT)
    expected = receipt.get("stageFiles", {})
    if receipt.get("repository") != PIN["repository"] or not isinstance(expected, dict) or not expected:
        raise ValueError("Unrecognized staged fork; it was preserved")
    actual = _tree(stage)
    actual.pop(RECEIPT, None)
    if any(name not in expected or expected[name] != value for name, value in actual.items()):
        raise ValueError("The staged fork changed; it was preserved")


def recover(root: Path) -> None:
    """Recover a folder swap after a process exit; refuse later external edits."""
    from .model import MODEL
    root = _safe_root(root)
    journal, stage = _paths(root)
    if not journal.exists():
        return
    MODEL.ensure_closed()
    state = read_json(journal)
    if state.get("repository") != PIN["repository"]:
        raise ValueError("Unrecognized fork installation journal")
    backup = root.with_name(root.name + (".lexeditor-original" if state["original"] else ".lexeditor-previous"))
    if root.exists():
        actual = _tree(root)
        if actual == state["after"]:
            # The new folder is fully in place. Finish retaining the bounded backup.
            if backup.exists():
                previous = _tree(backup)
                previous.pop(BACKUP, None)
                if previous != state["before"]:
                    raise ValueError("The fork backup changed; recovery was preserved")
                _write(backup / BACKUP, {"repository": PIN["repository"], "files": state["before"]})
            journal.unlink()
            return
        if actual != state["before"]:
            raise ValueError("The fork changed during installation; recovery was preserved")
    elif backup.exists():
        previous = _tree(backup)
        previous.pop(BACKUP, None)
        if previous != state["before"]:
            raise ValueError("The fork backup changed; recovery was preserved")
        (backup / BACKUP).unlink(missing_ok=True)
        backup.rename(root)
    elif state["before"]:
        raise ValueError("The fork recovery folder is missing")
    if stage.exists():
        if _tree(stage) != state["after"]:
            raise ValueError("The staged fork changed; it was preserved")
        shutil.rmtree(stage)
    journal.unlink()


def install(root: Path) -> dict:
    from .model import MODEL
    with MODEL.lock:
        MODEL.ensure_closed()
        root = _safe_root(root)
        root.parent.mkdir(parents=True, exist_ok=True)
        recover(root)
        if status(root)["installed"]:
            return status(root)
        if root.exists() and any(root.iterdir()):
            _verify_owned(root)
        journal, stage = _paths(root)
        if stage.exists():
            # Only a verified stage created by this installer may be evicted.
            _verify_stage(stage)
            shutil.rmtree(stage)
        if shutil.disk_usage(root.parent).free < 2 * PIN["unpackedLimit"] + PIN["bytes"]:
            raise OSError("The fork installation needs 370 MB of free temporary space")
        before = _tree(root) if root.exists() else {}
        try:
            with tempfile.TemporaryDirectory(prefix="lexeditor-verdite2-download-") as temporary:
                archive = Path(temporary) / PIN["asset"]
                url = f"https://github.com/{PIN['repository']}/releases/download/{PIN['tag']}/{PIN['asset']}"
                fetch_file(url, archive, limit=PIN["bytes"], label="Downloading Lexer's Verdite2 fork…")
                if archive.stat().st_size != PIN["bytes"] or digest(archive) != PIN["sha256"]:
                    raise ValueError("The fork download did not match the pinned size and SHA-256")
                with package_root(archive) as package:
                    files = file_tree(package)
                    if any(name.as_posix() in (RECEIPT, BACKUP) for name in files):
                        raise ValueError("The fork archive contains private installer state")
                    if sum((package / name).stat().st_size for name in files) > PIN["unpackedLimit"]:
                        raise ValueError("The unpacked fork exceeds its size limit")
                    if not all((package / name).is_file() for name in CRITICAL):
                        raise ValueError("The fork package is incomplete")
                    marker = read_json(package / "lexeditor-port.json")
                    if any(marker.get(key) != PIN[key] for key in ("repository", "sourceRevision", "serial", "version", "tag")):
                        raise ValueError("The fork package identifies a different build")
                    hashes = _tree(package)
                    owned = _verify_owned(root) if before else {}
                    extra = before.keys() - owned.keys() - {RECEIPT}
                    if set(extra) & hashes.keys():
                        raise ValueError("A player's file now collides with a fork file; preserve it before updating")
                    stage.mkdir()
                    _write(stage / RECEIPT, {"repository": PIN["repository"], "files": hashes,
                           "stageFiles": {**hashes, **{name: before[name] for name in extra}}})
                    shutil.copytree(package, stage, dirs_exist_ok=True)
            # Preserve files the player added, such as a ReShade configuration.
            for relative in extra:
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / relative, target)
            _verify_owned(stage)
            if before and _tree(root) != before:
                raise ValueError("The fork changed while preparing its update")
            after = _tree(stage)
            original = not root.with_name(root.name + ".lexeditor-original").exists()
            backup = root.with_name(root.name + (".lexeditor-original" if original else ".lexeditor-previous"))
            if before:
                _discard_backup(backup)
            _write(journal, {"repository": PIN["repository"], "original": original, "before": before, "after": after})
            MODEL.ensure_closed()
            if root.exists():
                if before:
                    root.rename(backup)
                else:
                    root.rmdir()
            stage.rename(root)
            recover(root)
        except BaseException:
            if journal.exists():
                recover(root)
            raise
        finally:
            if stage.exists() and not journal.exists():
                _verify_stage(stage)
                shutil.rmtree(stage)
        return status(root)
