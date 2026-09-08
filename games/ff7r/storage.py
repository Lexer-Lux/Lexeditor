"""Safe project-overlay reads and writes for FF7 Remake DataObjects."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from .archive import extract_pair
from .atb_dataobject import (
    is_atb_virtual_asset,
    load_atb_virtual_package,
    save_atb_virtual_package,
)
from .dataobject import DataObjectPackage, sha256_bytes
from .encounter_dataobject import (
    load_encounter_virtual_package,
    save_encounter_virtual_package,
)
from .encounter_tweaks import ENCOUNTER_TWEAKS_ASSET
from .graphics_dataobject import (
    load_graphics_virtual_package,
    save_graphics_virtual_package,
)
from .graphics_tweaks import GRAPHICS_TWEAKS_ASSET
from .runtime_dataobject import (
    NO_MORE_CHEATS_PROBE_ASSET,
    RUNTIME_PROBE_ASSET,
    RUNTIME_TWEAKS_ASSET,
    no_more_cheats_probe_package,
    runtime_probe_package,
    runtime_settings_package,
    save_runtime_edits,
)


def _project_target(project_root: Path, asset: str, suffix: str) -> Path:
    content = (Path(project_root).resolve() / "content").resolve()
    target = (content / (asset + suffix)).resolve()
    if target != content and content not in target.parents:
        raise ValueError(f"Unsafe FF7R project path: {asset}")
    return target


def load_package(game_root: Path, data_root: Path, project_root: Path,
                 index: dict, asset: str, *, vanilla: bool = False):
    if asset == RUNTIME_TWEAKS_ASSET:
        return runtime_settings_package(game_root, project_root, vanilla=vanilla)
    if asset == RUNTIME_PROBE_ASSET:
        return runtime_probe_package(game_root)
    if asset == NO_MORE_CHEATS_PROBE_ASSET:
        return no_more_cheats_probe_package(game_root, data_root, project_root, index)
    if is_atb_virtual_asset(asset):
        # ATB semantic views always compare against installed vanilla source;
        # project state lives in the separate reversible ATB config.
        return load_atb_virtual_package(game_root, data_root, project_root, index, asset)
    if asset == ENCOUNTER_TWEAKS_ASSET:
        return load_encounter_virtual_package(
            game_root, data_root, project_root, index, vanilla=vanilla)
    if asset == GRAPHICS_TWEAKS_ASSET:
        return load_graphics_virtual_package(
            game_root, project_root, vanilla=vanilla)

    source_uasset, source_uexp = extract_pair(game_root, data_root, index, asset)
    source_sha = sha256_bytes(source_uexp.read_bytes())
    project_uasset = _project_target(project_root, asset, ".uasset")
    project_uexp = _project_target(project_root, asset, ".uexp")
    using_project = not vanilla and project_uasset.is_file() and project_uexp.is_file()
    package = DataObjectPackage(
        project_uasset if using_project else source_uasset,
        project_uexp if using_project else source_uexp,
        asset=asset,
    )
    return package, source_sha, using_project


def save_edits(game_root: Path, data_root: Path, project_root: Path,
               index: dict, asset: str, *, source_sha256: str,
               active_sha256: str, edits: list[dict[str, Any]]) -> dict:
    if asset == RUNTIME_TWEAKS_ASSET:
        return save_runtime_edits(
            project_root,
            source_sha256=source_sha256,
            active_sha256=active_sha256,
            edits=edits,
        )
    if asset == RUNTIME_PROBE_ASSET:
        raise ValueError("FF7R Native Hook Probe is read-only")
    if asset == NO_MORE_CHEATS_PROBE_ASSET:
        raise ValueError("FF7R No More Cheats Probe is read-only")
    if is_atb_virtual_asset(asset):
        return save_atb_virtual_package(
            game_root, data_root, project_root, index, asset,
            source_sha256=source_sha256,
            active_sha256=active_sha256,
            edits=edits,
        )
    if asset == ENCOUNTER_TWEAKS_ASSET:
        return save_encounter_virtual_package(
            game_root, data_root, project_root, index,
            source_sha256=source_sha256,
            active_sha256=active_sha256,
            edits=edits,
        )
    if asset == GRAPHICS_TWEAKS_ASSET:
        return save_graphics_virtual_package(
            project_root,
            source_sha256=source_sha256,
            active_sha256=active_sha256,
            edits=edits,
        )

    package, actual_source_sha, using_project = load_package(
        game_root, data_root, project_root, index, asset, vanilla=False)
    if actual_source_sha != source_sha256:
        raise RuntimeError("Installed FF7R source data changed; reload this DataObject before saving")
    if sha256_bytes(package.uexp_bytes) != active_sha256:
        raise RuntimeError("The FF7R project DataObject changed on disk; reload before saving")
    package.apply_edits(edits)

    source_uasset, _source_uexp = extract_pair(game_root, data_root, index, asset)
    target_uasset = _project_target(project_root, asset, ".uasset")
    target_uexp = _project_target(project_root, asset, ".uexp")
    target_uasset.parent.mkdir(parents=True, exist_ok=True)
    if not target_uasset.is_file():
        shutil.copy2(source_uasset, target_uasset)
    original_size = len(package.uexp_bytes)
    package.write_uexp(target_uexp)
    if target_uexp.stat().st_size != original_size:
        raise RuntimeError("FF7R project write changed the fixed-size .uexp payload")
    verified = DataObjectPackage(target_uasset, target_uexp, asset=asset)
    if sha256_bytes(verified.uexp_bytes) != sha256_bytes(package.uexp_bytes):
        raise RuntimeError("FF7R project write failed binary readback verification")
    return {
        "asset": asset,
        "path": str(target_uexp),
        "saved": len(edits),
        "activeSha256": sha256_bytes(verified.uexp_bytes),
        "usingProject": True,
    }