"""Safe FFNx Direct Mode export/deployment for the shared FF7 editor.

The deployed surface follows current FFNx source behavior, not guessed archive
replacement rules:
- KERNEL sections 1..9 -> direct/kernel/kernel.bin.chunk.N
- KERNEL2 sections 1..18 -> direct/kernel/kernel.bin.chunk.10..27
- scene.bin 8192-byte blocks -> direct/battle/scene.bin.chunk.N
- field encounter section only -> direct/flevel.lgp/<field>.chunk.7
- world encounter member -> direct/world_us.lgp/enc_w.bin

Executable-backed edits remain project-only until FFNx exposes a documented
FF7 executable-data override contract.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile

from core.platform_config import load_config

from . import datasets, mod_stack, tooling
from .archives import LGP
from .battle import SceneArchive
from .extended import KernelText, resolve_source
from .format_codec import lzs_decode, read_int
from .kernel import resolve_kernel
from .storage import target_path


MANIFEST_NAME = ".lexeditor-ff7.json"
EXPORT_ROOT_NAME = ".lexeditor/ffnx-direct"
FFNX_SOURCE_REVISION = "b341cf135941ed745f89a5080a7cd95adb54018a"
PROCESS_NAMES = ("FFVII_LAUNCHER.exe", "FFVII.exe", "ff7.exe", "ff7_en.exe", "ff7_en")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative(value: str) -> Path:
    raw = str(value or "").strip().replace("\\", "/")
    path = Path(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ValueError("FFNx direct_mode_path must be a non-empty relative path")
    return path


def resolve_ffnx_config(game_root: Path) -> Path | None:
    """Return the one supported FFNx.toml location, or None when absent."""
    root = Path(game_root).resolve()
    candidates = (root / "FFNx.toml", root / "ff7" / "workingdir" / "FFNx.toml")
    found = [path for path in candidates if path.is_file()]
    if len(found) > 1:
        raise ValueError("Multiple FFNx.toml files were found; select one FF7 installation layout")
    return found[0] if found else None


def ffnx_config(game_root: Path) -> dict:
    path = resolve_ffnx_config(game_root)
    if path is None:
        expected = Path(game_root) / "FFNx.toml"
        return {
            "available": False, "runtime": "FFNx", "format": "toml",
            "path": str(expected), "sha256": None, "sections": [],
            "message": (
                "FFNx has not created FFNx.toml yet. Lexeditor checks the game root "
                "and ff7/workingdir. Saving and exporting keep working; "
                "deploying waits for that file."
            ),
        }
    result = load_config(path, "FFNx", "toml", game="FF7")
    result["baseDir"] = str(path.parent)
    return result


def _direct_root(game_root: Path) -> tuple[Path | None, dict]:
    config = ffnx_config(game_root)
    if not config.get("available"):
        return None, config
    fields = [field for section in config.get("sections", []) for field in section.get("fields", [])]
    direct = next((field.get("value") for field in fields if field.get("key") == "direct_mode_path"), "direct")
    if not isinstance(direct, str):
        raise ValueError("FFNx direct_mode_path is not a string")
    relative = _safe_relative(direct)
    base = Path(config["baseDir"]).resolve()
    root = (base / relative).resolve()
    if not root.is_relative_to(base):
        raise ValueError("FFNx direct_mode_path resolves outside the FFNx directory")
    return root, config


def _project_file(game_root: Path, project_root: Path, source: Path, relative: Path) -> Path:
    return target_path(game_root, project_root, source, relative)


def _kernel_chunks(game_root: Path, project_root: Path) -> tuple[dict[str, bytes], list[str]]:
    files: dict[str, bytes] = {}
    blocked: list[str] = []
    source, relative = resolve_kernel(game_root)
    project = _project_file(game_root, project_root, source, relative)
    if not project.is_file():
        return files, blocked
    vanilla = datasets.Kernel(source)
    active = datasets.Kernel(project)

    # Rebuild all modeled records from the vanilla source. A project carrying
    # any other kernel mutation is not silently sent to the game.
    expected = datasets.Kernel(source)
    for key in datasets.CATEGORIES:
        try:
            expected.apply(key, active.records(key))
        except (OSError, ValueError, EOFError, struct.error) as error:
            blocked.append(f"KERNEL.BIN cannot be proved safe for deployment: {key}: {error}")
            return files, blocked
    if any(bytes(a) != bytes(b) for a, b in zip(active.sections, expected.sections)):
        blocked.append("KERNEL.BIN contains changes outside Lexeditor's modeled FF7 fields")
        return files, blocked

    for index in range(9):
        current, original = bytes(active.sections[index]), bytes(vanilla.sections[index])
        if current != original:
            files[f"kernel/kernel.bin.chunk.{index + 1}"] = current

    # Sections 10..27 are loaded from KERNEL2 by the game/FFNx. Keep embedded
    # KERNEL text edits explicit instead of pretending those bytes deploy.
    changed_embedded = [index + 1 for index in range(9, 27)
                        if bytes(active.sections[index]) != bytes(vanilla.sections[index])]
    if changed_embedded:
        blocked.append(
            "KERNEL.BIN embedded text sections changed ("
            + ", ".join(map(str, changed_embedded))
            + "); edit/deploy the corresponding KERNEL2 Text records instead"
        )
    return files, blocked


def _text_chunks(game_root: Path, project_root: Path) -> tuple[dict[str, bytes], list[str]]:
    files: dict[str, bytes] = {}
    try:
        source, relative = resolve_source(game_root, "text")
    except (OSError, ValueError) as error:
        return files, [f"KERNEL2 deployment unavailable: {error}"]
    project = _project_file(game_root, project_root, source, relative)
    if not project.is_file():
        return files, []
    vanilla = KernelText(source.read_bytes())
    active = KernelText(project.read_bytes())
    if len(active.sections) != 18 or len(vanilla.sections) != 18:
        return files, ["KERNEL2 must contain exactly 18 text sections for FFNx Direct Mode"]
    # Repacking the complete decoded string set proves the file contains only
    # data this editor understands. Container/compression provenance is ignored.
    for index, (current, original) in enumerate(zip(active.sections, vanilla.sections)):
        if current != original:
            files[f"kernel/kernel.bin.chunk.{index + 10}"] = bytes(current)
    return files, []


def _scene_changed_outside_editor(vanilla: bytes, active: bytes) -> bool:
    # IDs at 0..7 and the attack-ID table at 0x840..0x87f are intentionally
    # not editable. Everything else below 0x1e80 is owned by the exposed scene
    # formation/enemy/attack/AI editors.
    return vanilla[:8] != active[:8] or vanilla[0x840:0x880] != active[0x840:0x880]


def _scene_chunks(game_root: Path, project_root: Path) -> tuple[dict[str, bytes], list[str]]:
    files: dict[str, bytes] = {}
    try:
        source, relative = resolve_source(game_root, "scene")
    except (OSError, ValueError) as error:
        return files, [f"scene.bin deployment unavailable: {error}"]
    project = _project_file(game_root, project_root, source, relative)
    if not project.is_file():
        return files, []
    vanilla = SceneArchive(source.read_bytes())
    active = SceneArchive(project.read_bytes())
    if len(active.scenes) != len(vanilla.scenes) or active.blocks != vanilla.blocks:
        return files, ["scene.bin layout differs from the installed source"]
    for index, (before, after) in enumerate(zip(vanilla.scenes, active.scenes)):
        if bytes(before) != bytes(after) and _scene_changed_outside_editor(bytes(before), bytes(after)):
            return files, [f"scene.bin scene {index} contains changes outside modeled editor ranges"]
    raw = project.read_bytes()
    original = source.read_bytes()
    if len(raw) != len(original) or len(raw) % 0x2000:
        return files, ["scene.bin project block layout is not deployable by FFNx"]
    for block in range(len(raw) // 0x2000):
        start = block * 0x2000
        current = raw[start:start + 0x2000]
        if current != original[start:start + 0x2000]:
            files[f"battle/scene.bin.chunk.{block}"] = current
    return files, []


def _field_sections(member: bytes) -> list[bytes]:
    raw = lzs_decode(member)
    if raw[:2] != b"\0\0" or read_int(raw, 2, 4) != 9:
        raise ValueError("expected a nine-section PC field")
    pointers = list(struct.unpack_from("<9I", raw, 6))
    if pointers != sorted(set(pointers)) or pointers[0] < 42:
        raise ValueError("invalid field section pointers")
    sections: list[bytes] = []
    for index, start in enumerate(pointers):
        size = read_int(raw, start, 4)
        end = start + 4 + size
        if end > len(raw) or (index < 8 and end > pointers[index + 1]):
            raise ValueError("invalid field section bounds")
        sections.append(bytes(raw[start + 4:end]))
    return sections


def _field_chunks(game_root: Path, project_root: Path) -> tuple[dict[str, bytes], list[str]]:
    files: dict[str, bytes] = {}
    try:
        source, relative = resolve_source(game_root, "field")
    except (OSError, ValueError) as error:
        return files, [f"flevel deployment unavailable: {error}"]
    project = _project_file(game_root, project_root, source, relative)
    if not project.is_file():
        return files, []
    vanilla, active = LGP(source.read_bytes()), LGP(project.read_bytes())
    if [row[0].casefold() for row in vanilla.entries] != [row[0].casefold() for row in active.entries]:
        return files, ["flevel.lgp member identity/order differs from the installed source"]
    for index, (name, _, _) in enumerate(vanilla.entries):
        before, after = vanilla.member(index), active.member(index)
        if before == after:
            continue
        try:
            old_sections, new_sections = _field_sections(before), _field_sections(after)
        except (ValueError, EOFError, struct.error) as error:
            return files, [f"flevel.lgp member {name} changed but is not a deployable PC field: {error}"]
        if any(old_sections[n] != new_sections[n] for n in range(9) if n != 6):
            return files, [f"flevel.lgp member {name} contains changes outside encounter section 7"]
        if old_sections[6] != new_sections[6]:
            files[f"flevel.lgp/{name}.chunk.7"] = new_sections[6]
    return files, []


def _world_chunks(game_root: Path, project_root: Path) -> tuple[dict[str, bytes], list[str]]:
    files: dict[str, bytes] = {}
    try:
        source, relative = resolve_source(game_root, "world")
    except (OSError, ValueError) as error:
        return files, [f"world encounter deployment unavailable: {error}"]
    project = _project_file(game_root, project_root, source, relative)
    if not project.is_file():
        return files, []
    vanilla, active = LGP(source.read_bytes()), LGP(project.read_bytes())
    if [row[0].casefold() for row in vanilla.entries] != [row[0].casefold() for row in active.entries]:
        return files, ["world_us.lgp member identity/order differs from the installed source"]
    changed: list[tuple[str, bytes]] = []
    for index, (name, _, _) in enumerate(vanilla.entries):
        before, after = vanilla.member(index), active.member(index)
        if before != after:
            changed.append((name, after))
    unsupported = [name for name, _ in changed if name.casefold() != "enc_w.bin"]
    if unsupported:
        return files, ["world_us.lgp contains unsupported changed members: " + ", ".join(unsupported)]
    for name, raw in changed:
        if len(raw) != 0x8A0:
            return files, ["enc_w.bin must contain exactly 2208 bytes"]
        files["world_us.lgp/enc_w.bin"] = raw
    return files, []


def _executable_blocker(game_root: Path, project_root: Path) -> list[str]:
    try:
        source, relative = resolve_source(game_root, "shop")
    except (OSError, ValueError):
        return []
    project = _project_file(game_root, project_root, source, relative)
    if project.is_file() and project.read_bytes() != source.read_bytes():
        return [
            "Executable-backed edits are saved in the project but are not deployable: "
            "current FFNx documents EXE Direct Mode data for FF8, not FF7. No executable is overwritten."
        ]
    return []


def build_plan(game_root: Path, project_root: Path) -> dict:
    game_root, project_root = Path(game_root).resolve(), Path(project_root).resolve()
    if project_root.is_relative_to(game_root):
        raise ValueError("FF7 deployment project must be outside the installed game")
    files: dict[str, bytes] = {}
    blocked: list[str] = []
    for producer in (_kernel_chunks, _text_chunks, _scene_chunks, _field_chunks, _world_chunks):
        generated, problems = producer(game_root, project_root)
        overlap = set(files) & set(generated)
        if overlap:
            raise ValueError("Multiple FF7 sources generated the same FFNx Direct path")
        files.update(generated)
        blocked.extend(problems)
    blocked.extend(_executable_blocker(game_root, project_root))
    direct_root, config = _direct_root(game_root)
    rows = [{"path": path, "bytes": len(data), "sha256": _digest(data)}
            for path, data in sorted(files.items())]
    ffnx_values = {
        field.get("key"): field.get("value")
        for section in config.get("sections", [])
        for field in section.get("fields", []) if field.get("key")
    }
    external_mods = mod_stack.configured_stack(files, ffnx_values=ffnx_values)
    return {
        "contract": "Lexeditor.ff7-ffnx-direct",
        "sourceRevision": FFNX_SOURCE_REVISION,
        "ready": not blocked,
        "blocked": blocked,
        "files": rows,
        "fileCount": len(rows),
        "bytes": sum(row["bytes"] for row in rows),
        "ffnx": {
            "available": bool(config.get("available")),
            "config": config.get("path"),
            "directRoot": str(direct_root) if direct_root else None,
            "message": config.get("message", ""),
        },
        "setup": tooling.helper_status(game_root),
        "externalMods": external_mods,
        "_payload": files,
    }


def _manifest(plan: dict) -> dict:
    return {
        "schema": 1,
        "plugin": "ff7",
        "sourceRevision": plan["sourceRevision"],
        "files": [{key: row[key] for key in ("path", "bytes", "sha256")} for row in plan["files"]],
    }


def export_project(game_root: Path, project_root: Path) -> dict:
    """Create a reproducible, isolated FFNx Direct tree inside the project."""
    plan = build_plan(game_root, project_root)
    if plan["blocked"]:
        raise ValueError("FF7 project has undeployable changes: " + " | ".join(plan["blocked"]))
    root = Path(project_root).resolve() / EXPORT_ROOT_NAME
    if root.exists():
        manifest = root / MANIFEST_NAME
        if not manifest.is_file():
            raise ValueError(f"Refusing to replace unowned export directory: {root}")
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    for relative, data in plan["_payload"].items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = _manifest(plan)
    (root / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    result = {key: value for key, value in plan.items() if key != "_payload"}
    result.update(exported=True, exportRoot=str(root), manifest=manifest)
    return result


def _read_manifest(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        raise ValueError(f"Invalid Lexeditor deployment manifest: {path}")
    if data.get("schema") != 1 or data.get("plugin") != "ff7" or not isinstance(data.get("files"), list):
        raise ValueError(f"Unsupported Lexeditor deployment manifest: {path}")
    return data


def deploy_project(game_root: Path, project_root: Path, running_check=None) -> dict:
    """Install only owned Direct Mode files; never replace archives/executables."""
    if running_check and running_check():
        raise RuntimeError("Close Final Fantasy VII before deploying FFNx Direct data")
    exported = export_project(game_root, project_root)
    external_overlaps = exported.get("externalMods", {}).get("overlaps", [])
    if external_overlaps:
        paths = sorted({row.get("path", "") for row in external_overlaps if row.get("path")})
        raise ValueError(
            "Active 7th Heaven folder mod(s) overlap Lexeditor FFNx Direct paths; "
            "deployment is blocked rather than guessing a winner: " + ", ".join(paths[:8])
            + (f" (+{len(paths) - 8} more)" if len(paths) > 8 else "")
        )
    direct_root = Path(exported["ffnx"]["directRoot"]) if exported["ffnx"]["directRoot"] else None
    if direct_root is None:
        raise ValueError("FFNx.toml is required before deployment")
    base = Path(exported["ffnx"]["config"]).parent.resolve()
    if not direct_root.resolve().is_relative_to(base):
        raise ValueError("FFNx Direct root resolves outside the FFNx directory")
    direct_root.mkdir(parents=True, exist_ok=True)
    manifest_path = direct_root / MANIFEST_NAME
    previous = _read_manifest(manifest_path)
    previous_files = {row["path"]: row for row in previous.get("files", []) if isinstance(row, dict) and "path" in row}
    new_files = {row["path"]: row for row in exported["files"]}

    # Preflight every collision/deletion before mutating anything.
    for relative, row in new_files.items():
        target = (direct_root / relative).resolve()
        if not target.is_relative_to(direct_root.resolve()):
            raise ValueError(f"Unsafe FFNx Direct path: {relative}")
        if target.exists():
            prior = previous_files.get(relative)
            if prior is None:
                raise ValueError(f"FFNx Direct path is already owned by another mod: {target}")
            if _digest(target.read_bytes()) != prior.get("sha256"):
                raise ValueError(f"Managed FFNx Direct file changed outside Lexeditor: {target}")
    for relative, row in previous_files.items():
        if relative in new_files:
            continue
        target = (direct_root / relative).resolve()
        if target.is_file() and _digest(target.read_bytes()) != row.get("sha256"):
            raise ValueError(f"Managed FFNx Direct file changed outside Lexeditor: {target}")

    backup: dict[Path, bytes | None] = {}
    try:
        for relative in set(previous_files) | set(new_files):
            target = (direct_root / relative).resolve()
            backup[target] = target.read_bytes() if target.is_file() else None
        for relative in set(previous_files) - set(new_files):
            (direct_root / relative).unlink(missing_ok=True)
        payload = exported["manifest"]
        source_root = Path(exported["exportRoot"])
        for relative in new_files:
            source = source_root / relative
            target = direct_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(source.read_bytes())
            os.replace(temporary, target)
        temporary_manifest = manifest_path.with_suffix(".tmp")
        temporary_manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary_manifest, manifest_path)
    except Exception:
        for target, raw in backup.items():
            if raw is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        raise
    return {**exported, "deployed": True, "directRoot": str(direct_root)}


def remove_deployment(game_root: Path) -> dict:
    direct_root, config = _direct_root(game_root)
    if direct_root is None:
        return {"removed": 0, "conflicts": [], "message": "FFNx.toml is unavailable."}
    manifest_path = direct_root / MANIFEST_NAME
    manifest = _read_manifest(manifest_path)
    if not manifest:
        return {"removed": 0, "conflicts": [], "message": "No Lexeditor FF7 deployment is recorded."}
    removed = 0
    conflicts: list[str] = []
    for row in manifest["files"]:
        relative = row.get("path")
        if not isinstance(relative, str):
            continue
        target = (direct_root / relative).resolve()
        if not target.is_relative_to(direct_root.resolve()):
            conflicts.append(relative)
            continue
        if not target.exists():
            continue
        if not target.is_file() or _digest(target.read_bytes()) != row.get("sha256"):
            conflicts.append(relative)
            continue
        target.unlink()
        removed += 1
    if not conflicts:
        manifest_path.unlink(missing_ok=True)
    return {
        "removed": removed, "conflicts": conflicts,
        "message": (
            "Removed only unchanged Lexeditor-owned FFNx Direct files."
            if not conflicts else
            "Some managed files were changed outside Lexeditor and were left in place."
        ),
    }
